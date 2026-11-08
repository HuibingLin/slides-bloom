#!/usr/bin/env python3
"""Convert a PPTX to an animation-aware PDF using the Slides Bloom HTTP API."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://slidesbloom.duckdns.org"


class ConversionError(Exception):
    pass


def api_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    # Python.org builds on macOS can lack their own CA bundle even when the
    # system CA bundle exists. Keep certificate verification enabled.
    if (sys.platform == "darwin" and not os.environ.get("SSL_CERT_FILE")
            and ssl.get_default_verify_paths().cafile is None
            and Path("/etc/ssl/cert.pem").is_file()):
        context.load_verify_locations(cafile="/etc/ssl/cert.pem")
    return context


def open_request(url: str, *, method: str = "GET", data: bytes | None = None,
                 headers: dict[str, str] | None = None, timeout: float = 120):
    request = Request(url, data=data, headers=headers or {}, method=method)
    try:
        return urlopen(request, timeout=timeout, context=tls_context())
    except HTTPError as exc:
        body = exc.read(4096)
        try:
            detail = json.loads(body).get("detail")
        except (ValueError, AttributeError):
            detail = None
        raise ConversionError(f"HTTP {exc.code} from {url}: {detail or exc.reason}") from exc
    except URLError as exc:
        raise ConversionError(f"Cannot reach {url}: {exc.reason}") from exc


def request_json(url: str, *, method: str = "GET", payload: dict | None = None,
                 timeout: float = 120) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else None
    with open_request(url, method=method, data=data, headers=headers, timeout=timeout) as response:
        try:
            result = json.load(response)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ConversionError(f"Invalid JSON from {url}") from exc
    if not isinstance(result, dict):
        raise ConversionError(f"Unexpected JSON from {url}")
    return result


def convert(source: Path, output: Path, base_url: str, poll_interval: float,
            max_wait: float, request_timeout: float, force: bool) -> dict:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".pptx":
        raise ConversionError("Input must be an existing .pptx file")
    if source == output:
        raise ConversionError("Output path must differ from input path")
    if output.exists() and not force:
        raise ConversionError(f"Output already exists: {output} (use --force to replace it)")

    size = source.stat().st_size
    health = request_json(api_url(base_url, "/api/health"), timeout=request_timeout)
    limit = health.get("max_file_size")
    if not isinstance(limit, int) or not 0 < size <= limit:
        raise ConversionError(f"File size must be between 1 and {limit} bytes")

    session = request_json(api_url(base_url, "/api/uploads"), method="POST",
                           payload={"filename": source.name, "size": size}, timeout=request_timeout)
    upload_id = session.get("upload_id")
    chunk_size = session.get("chunk_size")
    if not isinstance(upload_id, str) or not isinstance(chunk_size, int) or chunk_size <= 0:
        raise ConversionError("Upload API returned an invalid session")
    print(f"Uploading {source.name} (job {upload_id})", file=sys.stderr)

    with source.open("rb") as input_file:
        index = 0
        while chunk := input_file.read(chunk_size):
            headers = {"Content-Type": "application/octet-stream",
                       "X-Chunk-SHA256": hashlib.sha256(chunk).hexdigest()}
            url = api_url(base_url, f"/api/uploads/{upload_id}/chunks/{index}")
            with open_request(url, method="PUT", data=chunk, headers=headers,
                              timeout=request_timeout):
                pass
            index += 1
    if index != session.get("total_chunks"):
        raise ConversionError("Upload API returned an inconsistent chunk count")

    queued = request_json(api_url(base_url, f"/api/uploads/{upload_id}/complete"),
                          method="POST", timeout=request_timeout)
    job_id = queued.get("job_id")
    if not isinstance(job_id, str):
        raise ConversionError("Conversion API did not return a job ID")
    print(f"Waiting for conversion (job {job_id})", file=sys.stderr)

    deadline = time.monotonic() + max_wait
    previous = None
    while True:
        if time.monotonic() >= deadline:
            raise ConversionError(f"Timed out waiting for job {job_id}; it may still be running")
        job = request_json(api_url(base_url, f"/api/jobs/{job_id}"), timeout=request_timeout)
        state = job.get("state")
        progress = job.get("progress")
        if (state, progress) != previous:
            print(f"{state}: {progress}%", file=sys.stderr)
            previous = (state, progress)
        if state == "done":
            break
        if state == "failed":
            raise ConversionError(f"Conversion failed: {job.get('message') or job.get('error_code') or 'unknown error'}")
        if state not in ("queued", "processing"):
            raise ConversionError(f"Unexpected job state: {state}")
        time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=f".{output.name}.",
                                         suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            url = api_url(base_url, f"/api/jobs/{job_id}/download")
            with open_request(url, timeout=request_timeout) as response:
                first = response.read(5)
                if first != b"%PDF-":
                    raise ConversionError("Download did not contain a PDF")
                file.write(first)
                while block := response.read(1024 * 1024):
                    file.write(block)
        if output.exists() and not force:
            raise ConversionError(f"Output already exists: {output} (use --force to replace it)")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return {"output": str(output), "pages": job.get("pages"),
            "warnings": job.get("warnings") or [], "job_id": job_id}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Local .pptx file")
    parser.add_argument("--output", type=Path, help="PDF path (default: next to input)")
    parser.add_argument("--base-url", default=os.environ.get("SLIDES_BLOOM_URL", DEFAULT_BASE_URL),
                        help="Slides Bloom origin (default: public site)")
    parser.add_argument("--poll-interval", type=float, default=3, help="Seconds between status checks")
    parser.add_argument("--max-wait", type=float, default=7200, help="Maximum seconds to wait for a job")
    parser.add_argument("--request-timeout", type=float, default=120, help="HTTP request timeout in seconds")
    parser.add_argument("--force", action="store_true", help="Replace an existing output PDF")
    args = parser.parse_args()
    if args.poll_interval <= 0 or args.max_wait <= 0 or args.request_timeout <= 0:
        parser.error("timeouts and poll interval must be positive")
    output = args.output or args.input.with_name(args.input.stem + "-animation-steps.pdf")
    try:
        result = convert(args.input, output, args.base_url, args.poll_interval,
                         args.max_wait, args.request_timeout, args.force)
    except (ConversionError, OSError) as exc:
        print(f"Slides Bloom: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
