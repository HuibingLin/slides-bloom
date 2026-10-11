"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { languageNames, locales, Locale } from "../i18n";
import "./stats.css";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "";
const labels = {
  en: {
    back: "Back to Slides Bloom", title: "Private statistics", subtitle: "Visits and use of your conversion service.",
    key: "Owner access key", keyHint: "Use ADMIN_TOKEN from your server's .env file. The key stays in this tab's memory and is never saved in the browser.",
    unlock: "View statistics", signOut: "Lock dashboard", refresh: "Refresh", period: "Daily list",
    allTime: "All-time totals", last: "Last", days: "days", date: "Date (UTC)",
    visits: "Page views", uploads: "Uploads started", completed: "Conversions completed",
    failed: "Conversions failed", downloads: "PDF download requests",
    explanation: "Counts are anonymous. Page views include repeat visits and may include automated traffic. No IP addresses, file names, or presentation contents are stored here.",
    invalid: "The access key is incorrect.", unavailable: "Statistics are unavailable. Check the ADMIN_TOKEN and Redis settings on the server.",
    network: "Could not reach the statistics service.", loading: "Loading statistics…",
  },
  "zh-TW": {
    back: "返回 Slides Bloom", title: "私人統計", subtitle: "查看轉換服務的訪問與使用數量。",
    key: "管理者存取金鑰", keyHint: "請使用伺服器 .env 中的 ADMIN_TOKEN。金鑰只保留在這個分頁的記憶體，不會儲存在瀏覽器中。",
    unlock: "查看統計", signOut: "鎖定統計頁", refresh: "重新整理", period: "每日清單",
    allTime: "累計總數", last: "最近", days: "天", date: "日期（UTC）",
    visits: "頁面訪問", uploads: "開始上傳", completed: "轉換成功",
    failed: "轉換失敗", downloads: "PDF 下載請求",
    explanation: "統計為匿名計數。重複訪問會重複計算，也可能包含自動化流量；這裡不儲存 IP、檔名或簡報內容。",
    invalid: "存取金鑰不正確。", unavailable: "無法取得統計。請檢查伺服器的 ADMIN_TOKEN 與 Redis 設定。",
    network: "無法連接統計服務。", loading: "正在載入統計…",
  },
  "zh-CN": {
    back: "返回 Slides Bloom", title: "私人统计", subtitle: "查看转换服务的访问与使用数量。",
    key: "管理员访问密钥", keyHint: "请使用服务器 .env 中的 ADMIN_TOKEN。密钥只保留在当前标签页的内存中，不会存入浏览器。",
    unlock: "查看统计", signOut: "锁定统计页", refresh: "刷新", period: "每日列表",
    allTime: "累计总数", last: "最近", days: "天", date: "日期（UTC）",
    visits: "页面访问", uploads: "开始上传", completed: "转换成功",
    failed: "转换失败", downloads: "PDF 下载请求",
    explanation: "统计使用匿名计数。重复访问会重复计算，也可能包含自动化流量；这里不保存 IP、文件名或演示文稿内容。",
    invalid: "访问密钥不正确。", unavailable: "无法获取统计。请检查服务器上的 ADMIN_TOKEN 和 Redis 设置。",
    network: "无法连接统计服务。", loading: "正在加载统计…",
  },
} as const;

type Metric = "visits" | "uploads" | "completed" | "failed" | "downloads";
type Counts = Record<Metric, number>;
type Stats = { timezone: string; total: Counts; days: Array<Counts & { date: string }> };
const metrics: Metric[] = ["visits", "uploads", "completed", "failed", "downloads"];

export default function AdminPage() {
  const [locale, setLocale] = useState<Locale>("en");
  const [key, setKey] = useState("");
  const [activeKey, setActiveKey] = useState("");
  const [range, setRange] = useState(30);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<"invalid" | "unavailable" | "network" | null>(null);
  const [loading, setLoading] = useState(false);
  const t = (name: keyof typeof labels.en) => labels[locale][name];

  useEffect(() => {
    try {
      const saved = localStorage.getItem("slides-bloom:language");
      if (locales.some(value => value === saved)) setLocale(saved as Locale);
    } catch { /* English remains the default. */ }
  }, []);

  useEffect(() => { document.documentElement.lang = locale; }, [locale]);

  async function load(secret: string, days = range) {
    if (!secret) return;
    setLoading(true); setError(null);
    try {
      const response = await fetch(`${API}/api/admin/stats?days=${days}`, {
        headers: { Authorization: `Bearer ${secret}` },
        cache: "no-store",
      });
      if (!response.ok) {
        if (response.status === 401) { setActiveKey(""); setStats(null); setError("invalid"); }
        else setError("unavailable");
        return;
      }
      setStats(await response.json());
      setActiveKey(secret);
      setKey("");
    } catch { setError("network"); }
    finally { setLoading(false); }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void load(key.trim());
  }

  function chooseLocale(next: Locale) {
    setLocale(next);
    try { localStorage.setItem("slides-bloom:language", next); } catch {}
  }

  return <div className="stats-shell">
    <header className="stats-topbar">
      <Link href="/" className="stats-brand">Slides Bloom</Link>
      <div className="stats-top-actions">
        <Link href="/" className="stats-back">{t("back")}</Link>
        <select aria-label={labels[locale].title} value={locale} onChange={event => chooseLocale(event.target.value as Locale)}>
          {locales.map(value => <option key={value} value={value}>{languageNames[value]}</option>)}
        </select>
      </div>
    </header>
    <main className="stats-main">
      <div className="stats-heading">
        <div><span className="stats-eyebrow">SLIDES BLOOM · OWNER</span><h1>{t("title")}</h1><p>{t("subtitle")}</p></div>
        {stats && <button type="button" className="stats-lock" onClick={() => { setActiveKey(""); setStats(null); setError(null); }}>{t("signOut")}</button>}
      </div>
      {!stats ? <form className="stats-login" onSubmit={onSubmit}>
        <label htmlFor="owner-key">{t("key")}</label>
        <input id="owner-key" type="password" autoComplete="off" value={key} onChange={event => setKey(event.target.value)} required minLength={32}/>
        <p>{t("keyHint")}</p>
        {error && <div className="stats-error" role="alert">{t(error)}</div>}
        <button type="submit" disabled={loading}>{loading ? t("loading") : t("unlock")}</button>
      </form> : <>
        <div className="stats-toolbar">
          <span>{t("allTime")}</span>
          <button type="button" onClick={() => void load(activeKey)} disabled={loading}>{loading ? t("loading") : t("refresh")}</button>
        </div>
        {error && <div className="stats-error" role="alert">{t(error)}</div>}
        <div className="stats-cards">
          {metrics.map(metric => <div className="stats-card" key={metric}><span>{t(metric)}</span><strong>{stats.total[metric].toLocaleString(locale)}</strong></div>)}
        </div>
        <div className="stats-table-heading">
          <h2>{t("period")}</h2>
          <label>{t("last")} <select value={range} onChange={event => { const next = Number(event.target.value); setRange(next); void load(activeKey, next); }}><option value={7}>7</option><option value={30}>30</option><option value={90}>90</option></select> {t("days")}</label>
        </div>
        <div className="stats-table-wrap"><table>
          <thead><tr><th scope="col">{t("date")}</th>{metrics.map(metric => <th scope="col" key={metric}>{t(metric)}</th>)}</tr></thead>
          <tbody>{stats.days.map(day => <tr key={day.date}><th scope="row">{day.date}</th>{metrics.map(metric => <td key={metric}>{day[metric].toLocaleString(locale)}</td>)}</tr>)}</tbody>
        </table></div>
        <p className="stats-note">{t("explanation")}</p>
      </>}
    </main>
  </div>;
}
