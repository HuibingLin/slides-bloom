from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from zipfile import BadZipFile, ZipFile

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
MAX_FILE = 20 * 1024 * 1024
CHUNK_SIZE = 8 * 1024 * 1024
MAX_UNCOMPRESSED = 4 * 1024 * 1024 * 1024
MAX_ENTRIES = 20000
RETENTION_SECONDS = 24 * 60 * 60
ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


def job_dir(job_id: str) -> Path:
    if not ID_PATTERN.fullmatch(job_id):
        raise ValueError("无效任务编号")
    return DATA_DIR / job_id


def new_upload(filename: str, size: int) -> dict:
    if not filename.lower().endswith(".pptx") or size <= 0 or size > MAX_FILE:
        raise ValueError("请选择不超过 20MB 的 .pptx 文件")
    job_id = uuid.uuid4().hex
    folder = job_dir(job_id)
    (folder / "chunks").mkdir(parents=True)
    meta = {"id": job_id, "filename": Path(filename).name[:200], "size": size,
            "chunks": (size + CHUNK_SIZE - 1) // CHUNK_SIZE,
            "created_at": time.time(), "state": "uploading"}
    _write_meta(folder, meta)
    return meta


def _write_meta(folder: Path, meta: dict):
    temporary = folder / "meta.tmp"
    temporary.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, folder / "meta.json")


def read_meta(job_id: str) -> dict:
    try:
        return json.loads((job_dir(job_id) / "meta.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError("上传任务不存在或已过期")


@contextmanager
def locked(job_id: str):
    folder = job_dir(job_id)
    if not folder.exists():
        raise ValueError("上传任务不存在或已过期")
    with (folder / ".lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield folder
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def chunk_path(job_id: str, index: int) -> Path:
    return job_dir(job_id) / "chunks" / f"{index:05d}.part"


def expected_chunk_size(meta: dict, index: int) -> int:
    if index < 0 or index >= meta["chunks"]:
        raise ValueError("分片编号超出范围")
    return min(CHUNK_SIZE, meta["size"] - index * CHUNK_SIZE)


def uploaded_chunks(job_id: str) -> list[int]:
    meta = read_meta(job_id)
    return [i for i in range(meta["chunks"]) if chunk_path(job_id, i).is_file()
            and chunk_path(job_id, i).stat().st_size == expected_chunk_size(meta, i)]


def validate_pptx(path: Path):
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            if not {"[Content_Types].xml", "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"} <= names:
                raise ValueError("文件不是有效的 PPTX 演示文稿")
            entries = archive.infolist()
            if len(entries) > MAX_ENTRIES or sum(item.file_size for item in entries) > MAX_UNCOMPRESSED:
                raise ValueError("解压后文件超过安全上限")
            if any(item.flag_bits & 1 for item in entries):
                raise ValueError("不支持加密的 PPTX 文件")
            if any(item.file_size > 1024 * 1024 * 1024 for item in entries):
                raise ValueError("PPTX 中有超出安全上限的单个文件")
            if any(item.filename.endswith((".xml", ".rels")) and item.file_size > 64 * 1024 * 1024
                   for item in entries):
                raise ValueError("PPTX 中的 XML 内容超过安全上限")
    except BadZipFile as exc:
        raise ValueError("文件不是有效的 PPTX 演示文稿") from exc


def assemble(job_id: str) -> Path:
    with locked(job_id) as folder:
        meta = read_meta(job_id)
        if meta["state"] in {"queued", "processing", "done"}:
            return folder / "source.pptx"
        if meta["state"] != "uploading":
            raise ValueError("当前任务不能合并")
        if len(uploaded_chunks(job_id)) != meta["chunks"]:
            raise ValueError("仍有分片尚未上传")
        destination = folder / "source.pptx"
        temporary = folder / "source.tmp"
        digest = hashlib.sha256()
        with temporary.open("wb") as output:
            for i in range(meta["chunks"]):
                with chunk_path(job_id, i).open("rb") as part:
                    for block in iter(lambda: part.read(1024 * 1024), b""):
                        output.write(block)
                        digest.update(block)
        if temporary.stat().st_size != meta["size"]:
            temporary.unlink(missing_ok=True)
            raise ValueError("文件大小校验失败")
        try:
            validate_pptx(temporary)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        os.replace(temporary, destination)
        meta["state"] = "queued"
        meta["sha256"] = digest.hexdigest()
        _write_meta(folder, meta)
        shutil.rmtree(folder / "chunks", ignore_errors=True)
        return destination


def cleanup_expired() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    removed = 0
    now = time.time()
    for folder in DATA_DIR.iterdir():
        if not folder.is_dir() or not ID_PATTERN.fullmatch(folder.name):
            continue
        try:
            meta = read_meta(folder.name)
            if now - meta["created_at"] < RETENTION_SECONDS:
                continue
            with locked(folder.name):
                shutil.rmtree(folder, ignore_errors=True)
                removed += 1
        except (ValueError, FileNotFoundError, OSError):
            continue
    return removed
