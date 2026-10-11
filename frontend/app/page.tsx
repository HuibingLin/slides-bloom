"use client";

import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import { isMessageKey, languageNames, locales, Locale, MessageKey, translate } from "./i18n";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "";
const MAX_SIZE = 20 * 1024 * 1024;
type Phase = "idle" | "uploading" | "queued" | "processing" | "done" | "failed";
type Job = { id: string; state: Phase; progress: number; message: string; message_key?: string; error_code?: string; error_slide?: number; pages?: number; original_slides?: number; expanded_slides?: number; fallback_slides?: number[]; warnings?: string[] };
type UploadSession = { upload_id: string; chunk_size: number; total_chunks: number };

class UploadError extends Error {
  constructor(public code: MessageKey) { super(code); }
}

function Icon({ name, size = 24 }: { name: "upload" | "file" | "download" | "check" | "alert" | "close" | "arrow" | "eye" | "external"; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const paths = {
    upload: <><path d="M12 16V4m0 0L8 8m4-4 4 4"/><path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/></>,
    file: <><path d="M6 3h8l4 4v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"/><path d="M14 3v5h5M8 13h8M8 17h6"/></>,
    download: <><path d="M12 4v12m0 0-4-4m4 4 4-4"/><path d="M4 17v3h16v-3"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    alert: <><path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 9v5m0 3h.01"/></>,
    close: <path d="M5 5 19 19M19 5 5 19"/>,
    arrow: <path d="M4 12h16m0 0-6-6m6 6-6 6"/>,
    eye: <><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z"/><circle cx="12" cy="12" r="2.5"/></>,
    external: <><path d="M14 4h6v6m0-6-9 9"/><path d="M20 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h6"/></>,
  };
  return <svg {...common} aria-hidden="true">{paths[name]}</svg>;
}

async function responseError(response: Response): Promise<UploadError> {
  const headerCode = response.headers.get("X-Error-Code");
  if (isMessageKey(headerCode)) return new UploadError(headerCode);
  try {
    const data = await response.json();
    if (isMessageKey(data.code)) return new UploadError(data.code);
  } catch { /* The proxy may return a plain-text error. */ }
  return new UploadError(response.status === 413 ? "fileTooLarge" : "requestFailed");
}

function uploadChunk(url: string, chunk: Blob, signal: AbortSignal, onProgress: (loaded: number) => void, checksum?: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    if (checksum) xhr.setRequestHeader("X-Chunk-SHA256", checksum);
    xhr.upload.onprogress = event => onProgress(event.loaded);
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) { resolve(); return; }
      const headerCode = xhr.getResponseHeader("X-Error-Code");
      if (isMessageKey(headerCode)) { reject(new UploadError(headerCode)); return; }
      try {
        const code = JSON.parse(xhr.responseText).code;
        if (isMessageKey(code)) { reject(new UploadError(code)); return; }
      } catch { /* Nginx errors may not contain JSON. */ }
      reject(new UploadError(xhr.status === 413 ? "fileTooLarge" : "chunkFailed"));
    };
    xhr.onerror = () => reject(new UploadError("networkInterrupted"));
    xhr.onabort = () => reject(new DOMException("Aborted", "AbortError"));
    signal.addEventListener("abort", () => xhr.abort(), { once: true });
    if (signal.aborted) { xhr.abort(); return; }
    xhr.send(chunk);
  });
}

async function sha256(chunk: Blob): Promise<string | undefined> {
  if (!globalThis.crypto?.subtle) return undefined;
  const digest = await crypto.subtle.digest("SHA-256", await chunk.arrayBuffer());
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const previewRef = useRef<HTMLDialogElement>(null);
  const visitRecorded = useRef(false);
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<MessageKey | null>(null);
  const [locale, setLocale] = useState<Locale>("en");
  const [dragging, setDragging] = useState(false);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewPage, setPreviewPage] = useState(1);
  const [previewLoading, setPreviewLoading] = useState(true);
  const [previewFailed, setPreviewFailed] = useState(false);

  useEffect(() => {
    if (visitRecorded.current) return;
    visitRecorded.current = true;
    void fetch(`${API}/api/metrics/visit`, { method: "POST", keepalive: true }).catch(() => {});
  }, []);

  useEffect(() => {
    const dialog = previewRef.current;
    if (!dialog) return;
    if (previewOpen && !dialog.open) dialog.showModal();
    if (!previewOpen && dialog.open) dialog.close();
  }, [previewOpen, phase, uploadId]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("slides-bloom:language");
      if (locales.some(value => value === saved)) setLocale(saved as Locale);
    } catch { /* English remains the default. */ }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const t = (key: MessageKey, values?: Record<string, string | number>) => translate(locale, key, values);

  function chooseLocale(next: Locale) {
    setLocale(next);
    try { localStorage.setItem("slides-bloom:language", next); } catch { /* Still switch for this visit. */ }
  }

  useEffect(() => {
    if (!uploadId || !["queued", "processing"].includes(phase)) return;
    let active = true;
    const update = (data: Job) => {
      if (!active || !data.state) return;
      setJob(data); setProgress(data.progress ?? 0); setPhase(data.state);
      if (data.state === "failed") setError(isMessageKey(data.error_code) ? data.error_code : "conversionFailed");
    };
    const poll = async () => {
      try { const res = await fetch(`${API}/api/jobs/${uploadId}`); if (res.ok) update(await res.json()); }
      catch { /* WebSocket or next poll will retry. */ }
    };
    poll();
    const timer = window.setInterval(poll, 4000);
    const wsBase = new URL(API || location.origin, location.origin);
    wsBase.protocol = wsBase.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = new URL(`/api/jobs/${uploadId}/ws`, wsBase).toString();
    const socket = new WebSocket(wsUrl);
    socket.onmessage = event => { try { const data = JSON.parse(event.data); if (data.state) update(data); } catch {} };
    return () => { active = false; window.clearInterval(timer); socket.close(); };
  }, [uploadId, phase]);

  function choose(next: File | null) {
    if (!next) return;
    if (!next.name.toLowerCase().endsWith(".pptx")) { setError("invalidFile"); return; }
    if (next.size === 0) { setError("emptyFile"); return; }
    if (next.size > MAX_SIZE) { setError("fileTooLarge"); return; }
    setFile(next); setError(null); setProgress(0); setPhase("idle"); setJob(null); setUploadId(null); setPreviewOpen(false); setPreviewPage(1);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault(); setDragging(false); choose(event.dataTransfer.files[0]);
  }

  async function start() {
    if (!file) return;
    const controller = new AbortController(); abortRef.current = controller;
    setError(null); setPhase("uploading"); setProgress(0);
    const resumeKey = `slides-bloom:${file.name}:${file.size}:${file.lastModified}`;
    try {
      let session: UploadSession | null = null;
      let saved: string | null = null;
      try { saved = localStorage.getItem(resumeKey); } catch { /* Browser storage may be disabled. */ }
      if (saved) {
        try {
          const existing = JSON.parse(saved) as UploadSession;
          const check = await fetch(`${API}/api/uploads/${existing.upload_id}`, { signal: controller.signal });
          if (check.ok && (await check.json()).state === "uploading") session = existing;
        } catch { /* Start a fresh upload. */ }
      }
      if (!session) {
        const response = await fetch(`${API}/api/uploads`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename: file.name, size: file.size }), signal: controller.signal });
        if (!response.ok) throw await responseError(response);
        session = await response.json();
        try { localStorage.setItem(resumeKey, JSON.stringify(session)); } catch { /* Upload still works without resume storage. */ }
      }
      if (!session) throw new UploadError("cannotCreateUpload");
      const current = await fetch(`${API}/api/uploads/${session.upload_id}`, { signal: controller.signal });
      if (!current.ok) throw await responseError(current);
      const uploaded = new Set<number>((await current.json()).uploaded_chunks);
      const completed = new Set(uploaded);
      const partial = new Map<number, number>();
      const sizes = Array.from({ length: session.total_chunks }, (_, i) => Math.min(session!.chunk_size, file.size - i * session!.chunk_size));
      const updateProgress = () => {
        const bytes = sizes.reduce((sum, size, i) => sum + (completed.has(i) ? size : Math.min(partial.get(i) || 0, size)), 0);
        setProgress(Math.min(65, Math.round(bytes / file.size * 65)));
      };
      updateProgress();
      const remaining = sizes.map((_, i) => i).filter(i => !uploaded.has(i));
      let pointer = 0;
      const workers = Array.from({ length: Math.min(3, remaining.length) }, async () => {
        while (pointer < remaining.length) {
          const index = remaining[pointer++];
          const blob = file.slice(index * session!.chunk_size, Math.min(file.size, (index + 1) * session!.chunk_size));
          const checksum = await sha256(blob);
          await uploadChunk(`${API}/api/uploads/${session!.upload_id}/chunks/${index}`, blob, controller.signal,
            loaded => { partial.set(index, loaded); updateProgress(); }, checksum);
          completed.add(index); partial.delete(index); updateProgress();
        }
      });
      await Promise.all(workers);
      const response = await fetch(`${API}/api/uploads/${session.upload_id}/complete`, { method: "POST", signal: controller.signal });
      if (!response.ok) throw await responseError(response);
      try { localStorage.removeItem(resumeKey); } catch { /* Ignore unavailable storage. */ }
      setUploadId(session.upload_id); setPhase("queued"); setProgress(68);
    } catch (cause) {
      controller.abort();
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      setPhase("failed"); setError(cause instanceof UploadError ? cause.code : cause instanceof TypeError ? "networkInterrupted" : "requestFailed");
    }
  }

  function reset() {
    abortRef.current?.abort(); setFile(null); setJob(null); setError(null); setPhase("idle"); setProgress(0); setUploadId(null); setPreviewOpen(false); setPreviewPage(1);
    if (inputRef.current) inputRef.current.value = "";
  }

  const active = phase === "uploading" || phase === "queued" || phase === "processing";
  const statusKey: MessageKey = isMessageKey(job?.message_key) ? job.message_key
    : phase === "processing" ? (job?.progress ?? 0) >= 85 ? "rendering" : "analyzing" : "waiting";
  const fallbackSlides = job?.fallback_slides ?? [];
  const previewUrl = uploadId ? `${API}/api/jobs/${uploadId}/preview` : "";
  const totalPages = Math.max(1, job?.pages ?? 1);
  function showPreviewPage(page: number) {
    if (page < 1 || page > totalPages || page === previewPage) return;
    setPreviewLoading(true);
    setPreviewFailed(false);
    setPreviewPage(page);
  }
  const previewSteps: MessageKey[] = ["stepOne", "stepTwo", "stepThree"];
  const previewLabels: MessageKey[] = ["beforeClick", "firstClick", "secondClick", "thirdClick"];
  return <div className="site-shell">
    <title>{t("title")}</title>
    <meta name="description" content={t("description")}/>
    <header className="topbar"><div className="brand"><span className="brand-mark"><span>1</span><span>2</span><span>3</span></span><span>Slides Bloom</span></div><div className="topbar-actions"><span className="topbar-note">{t("topNote")}</span><label className="language-control"><span className="sr-only">{t("language")}</span><select aria-label={t("language")} value={locale} onChange={event => chooseLocale(event.target.value as Locale)}>{locales.map(value => <option key={value} value={value}>{languageNames[value]}</option>)}</select></label></div></header>
    <main className="main-grid">
      <section className="workspace" aria-labelledby="headline">
        <div className="eyebrow"><span className="eyebrow-line"/> {t("eyebrow")}</div>
        <h1 id="headline">{t("headlineFirst")}<br/><em>{t("headlineSecond")}</em></h1>
        <p className="lead">{t("lead")}</p>
        <div className="upload-panel">
          <div className="panel-heading"><span>{t("uploadHeading")}</span><span className="panel-step">01 / 02</span></div>
          <input ref={inputRef} className="sr-only" type="file" accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation" onChange={(event: ChangeEvent<HTMLInputElement>) => choose(event.target.files?.[0] || null)}/>
          {!file ? <div className={`dropzone ${dragging ? "dragging" : ""}`} role="button" tabIndex={0} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") inputRef.current?.click(); }} onClick={() => inputRef.current?.click()} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
            <div className="upload-icon"><Icon name="upload" size={30}/></div>
            <strong>{t("dropTitle")}</strong><span>{t("or")} <u>{t("browse")}</u></span>
            <small>{t("uploadHint")}</small>
          </div> : <div className="selected-file"><div className="file-icon"><Icon name="file" size={28}/></div><div className="file-info"><strong title={file.name}>{file.name}</strong><span>{(file.size / 1024 / 1024).toFixed(1)} MB · {t("fileType")}</span></div><button className="icon-button" onClick={reset} disabled={phase === "processing" || phase === "queued"} aria-label={t("removeFile")}><Icon name="close" size={18}/></button></div>}
          {error && <div className="error-box" role="alert"><Icon name="alert" size={18}/>{t(error, { slide: job?.error_slide ?? "?" })}</div>}
          {file && phase === "idle" && <button className="primary-button" onClick={start}>{t("start")} <Icon name="arrow" size={19}/></button>}
          {file && phase === "failed" && <button className="primary-button" onClick={start}>{t("retry")} <Icon name="arrow" size={19}/></button>}
          {active && <div className="progress-area"><div className="progress-copy"><span>{phase === "uploading" ? t("uploading", { percent: Math.round(progress / 65 * 100) }) : t(statusKey)}</span><b>{progress}%</b></div><div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><span style={{ width: `${progress}%` }}/></div><small>{t(phase === "uploading" ? "uploadProgressHint" : "processProgressHint")}</small></div>}
          {phase === "done" && uploadId && <div className="result">
            <div className="result-top"><span className="success-icon"><Icon name="check" size={20}/></span><div><strong>{t("complete")}</strong><span>{t("resultSummary", { slides: job?.original_slides ?? 0, pages: job?.pages ?? 0 })}</span></div></div>
            <div className="result-actions">
              <button className="preview-button" type="button" onClick={() => { setPreviewPage(1); setPreviewLoading(true); setPreviewFailed(false); setPreviewOpen(true); }}><Icon name="eye" size={19}/> {t("previewPdf")}</button>
              <a className="download-button" href={`${API}/api/jobs/${uploadId}/download?lang=${locale}`}><Icon name="download" size={19}/> {t("download")}</a>
            </div>
            {(fallbackSlides.length > 0 || Boolean(job?.warnings?.length)) && <p className="warning"><Icon name="alert" size={16}/>{fallbackSlides.length > 0 ? t("fallbackWarning", { slides: fallbackSlides.join(", ") }) : t("fallbackWarningGeneric")}</p>}
            <button className="text-button" onClick={reset}>{t("convertAnother")}</button>
          </div>}
          <div className="upload-foot"><span><Icon name="check" size={15}/> {t("deletion")}</span><span>{t("noAccount")}</span></div>
        </div>
        <div className="notice"><span className="notice-symbol">i</span><p>{t("notice")}</p></div>
      </section>
      <aside className="explainer" aria-label={t("previewAria")}>
        <div className="preview-header"><span>{t("previewHeading")}</span><span className="preview-index">{t("previewCount")}</span></div>
        <div className="slide-stack">
          {previewLabels.map((label, index) => <div className="mini-slide" key={label}><div className="slide-label">{String(index + 1).padStart(2, "0")} <span>{t(label)}</span></div><div className="mini-title">{t("previewTitle")}</div><div className="mini-rule"/>{previewSteps.slice(0, index).map((step, stepIndex) => <p key={step}><b>{stepIndex + 1}.</b> {t(step)}</p>)}</div>)}
        </div>
        <div className="preview-bottom"><span className="tiny-dot"/> {t("previewFoot")}</div>
      </aside>
    </main>
    {phase === "done" && uploadId && <dialog ref={previewRef} className="pdf-dialog" aria-label={t("previewPdf")} onClose={() => setPreviewOpen(false)} onClick={event => { if (event.target === event.currentTarget) setPreviewOpen(false); }}>
      <div className="pdf-dialog-header">
        <div className="pdf-dialog-title"><strong>{t("previewPdf")}</strong><span>{t("resultSummary", { slides: job?.original_slides ?? 0, pages: job?.pages ?? 0 })}</span></div>
        <div className="pdf-dialog-actions"><a href={previewUrl} target="_blank" rel="noopener noreferrer"><Icon name="external" size={17}/> {t("openPreviewTab")}</a><a href={`${API}/api/jobs/${uploadId}/download?lang=${locale}`}><Icon name="download" size={17}/> {t("download")}</a><button type="button" onClick={() => setPreviewOpen(false)} aria-label={t("closePreview")}><Icon name="close" size={22}/></button></div>
      </div>
      {previewOpen && <div className="pdf-preview-stage">
        {previewLoading && !previewFailed && <span className="pdf-preview-loading" role="status">{t("previewLoading")}</span>}
        {previewFailed ? <p className="pdf-preview-error" role="alert">{t("previewUnavailable")}</p>
          : <img className="pdf-preview-image" key={previewPage} src={`${previewUrl}/pages/${previewPage}`} alt={t("previewPageAlt", { page: previewPage })} onLoad={() => setPreviewLoading(false)} onError={() => { setPreviewLoading(false); setPreviewFailed(true); }}/>}
      </div>}
      <div className="pdf-dialog-footer">
        <button type="button" onClick={() => showPreviewPage(previewPage - 1)} disabled={previewPage === 1}>{t("previousPage")}</button>
        <span>{t("pageOf", { page: previewPage, pages: totalPages })}</span>
        <button type="button" onClick={() => showPreviewPage(previewPage + 1)} disabled={previewPage === totalPages}>{t("nextPage")}</button>
      </div>
    </dialog>}
    <footer className="footer"><span>Slides Bloom <span className="footer-sep">/</span> {t("footerName")}</span><span>{t("footerDetail")}</span></footer>
  </div>;
}
