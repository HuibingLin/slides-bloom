from __future__ import annotations

import json
import os
import uuid
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium
import redis
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from .analytics import record_metric, require_admin, snapshot
from .errors import error_code
from .storage import CHUNK_SIZE, MAX_FILE, assemble, chunk_path, expected_chunk_size, job_dir, locked, new_upload, read_meta, uploaded_chunks
from .worker import REDIS_URL, convert, set_status

app = FastAPI(title="Slides Bloom", version="0.1.0")
origins = [origin.strip() for origin in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT"],
                   allow_headers=["Content-Type", "X-Chunk-SHA256", "Authorization"], expose_headers=["X-Error-Code"])


@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    declared = request.headers.get("content-length")
    try:
        too_large = declared is not None and int(declared) > MAX_FILE
    except ValueError:
        return JSONResponse({"detail": "无效的 Content-Length", "code": "invalidLength"}, status_code=400)
    if too_large:
        return JSONResponse({"detail": "请求体超过 20MB 上限", "code": "requestTooLarge"}, status_code=413)
    return await call_next(request)


class UploadRequest(BaseModel):
    filename: str
    size: int


def bad_request(exc: ValueError):
    return HTTPException(status_code=400, detail=str(exc), headers={"X-Error-Code": error_code(str(exc))})


@app.get("/api/health")
def health():
    return {"ok": True, "max_file_size": MAX_FILE, "chunk_size": CHUNK_SIZE}


@app.post("/api/metrics/visit", status_code=204)
def record_page_visit():
    record_metric("visits")
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@app.get("/api/admin/stats")
def private_stats(request: Request, days: int = 30):
    require_admin(request)
    try:
        data = snapshot(days)
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Statistics are temporarily unavailable")
    return JSONResponse(data, headers={"Cache-Control": "private, no-store",
                                       "X-Content-Type-Options": "nosniff",
                                       "Vary": "Authorization"})


@app.post("/api/uploads")
def create_upload(body: UploadRequest):
    try:
        meta = new_upload(body.filename, body.size)
        record_metric("uploads")
        return {"upload_id": meta["id"], "chunk_size": CHUNK_SIZE, "total_chunks": meta["chunks"]}
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/uploads/{upload_id}")
def get_upload(upload_id: str):
    try:
        meta = read_meta(upload_id)
        return {"upload_id": upload_id, "state": meta["state"], "uploaded_chunks": uploaded_chunks(upload_id),
                "total_chunks": meta["chunks"], "chunk_size": CHUNK_SIZE}
    except ValueError as exc:
        raise bad_request(exc)


@app.put("/api/uploads/{upload_id}/chunks/{index}")
async def put_chunk(upload_id: str, index: int, request: Request):
    try:
        meta = read_meta(upload_id)
        expected = expected_chunk_size(meta, index)
        if meta["state"] != "uploading":
            raise ValueError("上传已结束")
        if request.headers.get("content-length") and int(request.headers["content-length"]) > expected:
            raise ValueError("分片大小超出限制")
        destination = chunk_path(upload_id, index)
        temporary = destination.with_name(f"{index:05d}.{uuid.uuid4().hex}.tmp")
        import hashlib
        digest = hashlib.sha256()
        length = 0
        try:
            with temporary.open("wb") as out:
                async for block in request.stream():
                    length += len(block)
                    if length > expected:
                        raise ValueError("分片大小超出限制")
                    digest.update(block)
                    out.write(block)
            if length != expected:
                temporary.unlink(missing_ok=True)
                raise ValueError("分片长度不正确")
            claimed = request.headers.get("x-chunk-sha256")
            if claimed and digest.hexdigest() != claimed.lower():
                raise ValueError("分片校验失败")
            with locked(upload_id):
                if read_meta(upload_id)["state"] != "uploading":
                    raise ValueError("上传已结束")
                if not destination.exists() or destination.stat().st_size != expected:
                    os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return {"index": index, "received": length}
    except (ValueError, FileNotFoundError) as exc:
        raise bad_request(ValueError(str(exc)))


@app.post("/api/uploads/{upload_id}/complete")
def complete_upload(upload_id: str):
    try:
        meta = read_meta(upload_id)
        if meta["state"] == "uploading":
            assemble(upload_id)
        elif meta["state"] != "queued":
            return {"job_id": upload_id}
        connection = redis.Redis.from_url(REDIS_URL)
        if connection.set(f"dispatch:{upload_id}", "1", nx=True, ex=25 * 3600):
            try:
                set_status(upload_id, "queued", 68, "文件已上传，等待转换", message_key="waiting")
                convert.apply_async(args=[upload_id], task_id=upload_id)
            except Exception:
                connection.delete(f"dispatch:{upload_id}")
                raise
        return {"job_id": upload_id}
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    try:
        read_meta(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc), headers={"X-Error-Code": error_code(str(exc))})
    connection = aioredis.from_url(REDIS_URL)
    try:
        value = await connection.get(f"job:{job_id}")
        return json.loads(value) if value else {"id": job_id, "state": "queued", "progress": 68, "message": "等待转换", "message_key": "waiting"}
    finally:
        await connection.aclose()


@app.websocket("/api/jobs/{job_id}/ws")
async def job_events(socket: WebSocket, job_id: str):
    try:
        read_meta(job_id)
    except ValueError:
        await socket.close(code=1008)
        return
    await socket.accept()
    connection = aioredis.from_url(REDIS_URL)
    pubsub = connection.pubsub()
    try:
        await pubsub.subscribe(f"job-events:{job_id}")
        current = await connection.get(f"job:{job_id}")
        if current:
            await socket.send_text(current.decode())
        while True:
            event = await pubsub.get_message(ignore_subscribe_messages=True, timeout=20)
            if event and event["type"] == "message":
                await socket.send_text(event["data"].decode())
            else:
                await socket.send_json({"type": "heartbeat"})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await pubsub.aclose()
        await connection.aclose()


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str, lang: str = "en"):
    try:
        meta = read_meta(job_id)
        path = job_dir(job_id) / "result.pdf"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="PDF 尚未生成", headers={"X-Error-Code": "pdfNotReady"})
        suffix = {"en": "-animation-steps.pdf", "zh-TW": "-動畫展開.pdf", "zh-CN": "-动画展开.pdf"}.get(lang, "-animation-steps.pdf")
        filename = Path(meta["filename"]).stem + suffix
        record_metric("downloads")
        return FileResponse(path, media_type="application/pdf", filename=filename,
                            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc), headers={"X-Error-Code": error_code(str(exc))})


@app.get("/api/jobs/{job_id}/preview")
def preview(job_id: str):
    try:
        read_meta(job_id)
        path = job_dir(job_id) / "result.pdf"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="PDF 尚未生成", headers={"X-Error-Code": "pdfNotReady"})
        return FileResponse(path, media_type="application/pdf", filename="slides-bloom-preview.pdf",
                            content_disposition_type="inline",
                            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc), headers={"X-Error-Code": error_code(str(exc))})


@app.get("/api/jobs/{job_id}/preview/pages/{page_number}")
def preview_page(job_id: str, page_number: int):
    try:
        read_meta(job_id)
        path = job_dir(job_id) / "result.pdf"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="PDF 尚未生成", headers={"X-Error-Code": "pdfNotReady"})
        document = pdfium.PdfDocument(str(path))
        try:
            if page_number < 1 or page_number > len(document):
                raise HTTPException(status_code=404, detail="PDF 页码无效", headers={"X-Error-Code": "invalidPreviewPage"})
            page = document[page_number - 1]
            try:
                scale = min(1600 / max(page.get_width(), 1), 2400 / max(page.get_height(), 1))
                bitmap = page.render(scale=scale)
                try:
                    data = BytesIO()
                    bitmap.to_pil().save(data, format="PNG", optimize=True)
                finally:
                    bitmap.close()
            finally:
                page.close()
        finally:
            document.close()
        return Response(data.getvalue(), media_type="image/png",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc), headers={"X-Error-Code": error_code(str(exc))})
