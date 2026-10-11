from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import redis
from celery import Celery
from celery.schedules import crontab
from pypdf import PdfReader

from .analytics import record_job_outcome
from .errors import error_code
from .expand import UnsupportedAnimationError, expand_pptx
from .storage import DATA_DIR, cleanup_expired, job_dir

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
queue = Celery("slides_bloom", broker=REDIS_URL, backend=REDIS_URL)
queue.conf.update(task_acks_late=True, worker_prefetch_multiplier=1,
                  task_time_limit=7200, task_soft_time_limit=6900,
                  beat_schedule={"delete-expired-files-hourly": {
                      "task": "app.worker.cleanup", "schedule": crontab(minute=0)}})


def set_status(job_id: str, state: str, progress: int, message: str, **extra):
    connection = redis.Redis.from_url(REDIS_URL)
    try:
        payload = {"id": job_id, "state": state, "progress": progress, "message": message, **extra}
        connection.setex(f"job:{job_id}", 25 * 3600, json.dumps(payload, ensure_ascii=False))
        connection.publish(f"job-events:{job_id}", json.dumps(payload, ensure_ascii=False))
        record_job_outcome(connection, job_id, state)
    finally:
        connection.close()


@queue.task(name="app.worker.convert", bind=True)
def convert(self, job_id: str):
    folder = job_dir(job_id)
    source = folder / "source.pptx"
    intermediate = folder / "expanded.pptx"
    output = folder / "result.pdf"
    try:
        set_status(job_id, "processing", 72, "正在分析动画步骤", message_key="analyzing")
        report = expand_pptx(source, intermediate)
        set_status(job_id, "processing", 85, f"已展开为 {report.output_pages} 页，正在渲染 PDF", message_key="rendering")
        with tempfile.TemporaryDirectory(prefix="lo-profile-", dir=folder) as profile:
            command = ["soffice", f"-env:UserInstallation=file://{profile}", "--headless", "--convert-to",
                       "pdf:impress_pdf_Export", "--outdir", str(folder), str(intermediate)]
            run = subprocess.run(command, capture_output=True, text=True, timeout=5400,
                                 env={**os.environ, "HOME": str(folder)})
        rendered = folder / "expanded.pdf"
        if run.returncode != 0 or not rendered.exists() or rendered.stat().st_size == 0:
            raise RuntimeError("LibreOffice 渲染失败：" + (run.stderr or run.stdout)[-500:])
        pages = len(PdfReader(str(rendered)).pages)
        if pages != report.output_pages:
            raise RuntimeError(f"PDF 页数校验失败：预期 {report.output_pages}，实际 {pages}")
        os.replace(rendered, output)
        intermediate.unlink(missing_ok=True)
        set_status(job_id, "done", 100, "转换完成", message_key="complete", pages=pages,
                   original_slides=report.original_slides,
                   expanded_slides=report.expanded_slides,
                   fallback_slides=report.fallback_slides,
                   warnings=report.warnings)
    except Exception as exc:
        intermediate.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
        extra = {"error_slide": exc.slide_number} if isinstance(exc, UnsupportedAnimationError) else {}
        set_status(job_id, "failed", 0, str(exc)[:500], error_code=error_code(str(exc)), **extra)
        raise


@queue.task(name="app.worker.cleanup")
def cleanup():
    return cleanup_expired()
