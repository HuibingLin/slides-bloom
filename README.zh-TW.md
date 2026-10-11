# Slides Bloom

[English](README.md) · **繁體中文** · [简体中文](README.zh-CN.md)

## 直接線上使用

**網站網址：** `https://slidesbloom.duckdns.org/`

[開啟 Slides Bloom 線上版](https://slidesbloom.duckdns.org/)

在瀏覽器輸入上方網址，或點擊連結，即可上傳 PowerPoint（`.pptx`）、將點擊動畫轉換為逐頁 PDF、預覽並下載結果。網站免費使用，無須安裝軟體或註冊帳號。

**將 PPTX 的點擊動畫展開為可逐頁閱讀的 PDF。** Slides Bloom 是免費、開源、可自行部署的工具。上傳簡報後，它會依原始動畫順序產生每次點擊後的累積畫面，讓講義或分享用 PDF 保留講述節奏。

## 轉換結果是什麼樣子？

假設一張投影片有依序出現的 ①、②、③，輸出的 PDF 會有四頁：

![一張投影片的三次點擊依序展開成四頁 PDF，已出現的項目會保留](docs/images/animation-steps.svg)

```text
第 1 頁  原始起始畫面，尚未點擊
第 2 頁  起始畫面 + ①
第 3 頁  起始畫面 + ① + ②
第 4 頁  起始畫面 + ① + ② + ③
```

沒有支援動畫的靜態投影片仍輸出一頁。若同一次點擊包含多個同步或接續的進入效果，這些效果會出現在同一頁。展開後的頁面會維持原投影片順序。

## 主要功能

- 上傳最大 **20 MiB**（介面標示 20 MB）的 `.pptx`；以 8 MiB 分片傳輸，網路中斷後重新選擇同一檔案即可續傳。
- 後台非同步分析動畫並使用 LibreOffice Impress 產生 PDF；介面顯示上傳與轉換進度。
- 完成後可在網站內**逐頁預覽 PDF**，也可在新分頁開啟完整 PDF 或直接下載。
- 介面提供 English、繁體中文、简体中文；首次開啟預設英文，語言選擇保存在瀏覽器中。
- 上傳檔案及產出的 PDF 在建立任務滿 24 小時後，由每小時執行的清理工作移除。

## 技術架構

- **前端：** Next.js 15、React 19、TypeScript 與 CSS。介面建構為靜態網站。
- **API 與文件處理：** Python 3.12 與 FastAPI 負責上傳、任務狀態及 PDF 預覽；`lxml` 讀取與修改 PPTX 動畫資料，LibreOffice Impress 將展開後的投影片轉換為 PDF，`pypdf` 與 `pypdfium2` 用於 PDF 處理與預覽。
- **背景工作與儲存：** Celery 負責轉換與定時清理；Redis 保存任務佇列與進度。上傳檔案及 PDF 暫存於設定的資料目錄，到期後清理。

## 快速啟動

需要 Docker、Docker Compose，以及足夠的可用記憶體和磁碟空間。Worker 的記憶體上限為 6 GB；建議讓 Docker 有超過 6 GB 的可用記憶體。解壓與渲染所需空間可能遠大於原始 PPTX，請將資料目錄放在空間充足的本機 SSD。

在專案根目錄執行：

```sh
cp -n .env.example .env
docker compose up --build -d
```

開啟 [http://localhost:8080](http://localhost:8080)。若需要更改對外連接埠或資料位置，先編輯 `.env`：

```dotenv
PORT=8080
DATA_PATH=./data
```

`DATA_PATH` 存放上傳分片、原始檔與 PDF。停止服務可執行 `docker compose down`；這不會刪除 `DATA_PATH` 中尚未到期的資料。自動清理需要 `beat` 服務持續運作。

### 確認服務正常

```sh
docker compose ps
curl http://localhost:8080/api/health
```

接著在頁面上傳一份含點擊進入動畫的 PPTX。若一張投影片有三次點擊，預覽中應看到其起始畫面及三個累積狀態，共四頁。需要查看處理紀錄時可執行 `docker compose logs -f worker`。

## 系統組成

![從 PPTX 分片上傳，經 FastAPI、Celery 與 Redis、LibreOffice，到 PDF 預覽與下載的處理流程](docs/images/conversion-flow.svg)

- **Next.js**：將上傳、進度、語言切換、PDF 預覽與下載介面建置為靜態檔案，由 Nginx 提供；正式環境不常駐執行 Node.js 服務。
- **Nginx / FastAPI**：網頁與 API 入口、分片接收、檔案驗證、任務查詢及預覽圖片。
- **Celery / Redis**：背景轉換與進度通知。Worker 預設一次處理 1 個任務，容器記憶體上限為 6 GB，單一任務最長 2 小時；後續上傳會排隊。
- **Celery Beat**：每小時清理建立時間已超過 24 小時的任務檔案。

Nginx 的單一請求體上限為 20 MiB；每個上傳分片小於此限制。上傳時也會檢查 PPTX 格式與解壓後的安全上限，因此 20 MiB 是**檔案上傳上限**，不代表每個 20 MiB 的檔案都能在特定主機資源下完成轉換。

## 本地開發與測試

最簡單的方式是先用上述 Compose 指令啟動全部服務。若要在本機執行前端開發伺服器：

```sh
cd frontend
npm ci
NEXT_PUBLIC_API_BASE=http://localhost:8080 npm run dev
```

開發介面位於 [http://localhost:3000](http://localhost:3000)，API 仍由 Compose 的 `localhost:8080` 提供。前端正式建置可執行 `npm run build`。

執行後端測試：

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -v
```

測試涵蓋 20 MiB 限制、動畫累積頁面、公式圖片遮罩及不支援動畫的錯誤處理。完整的上傳至 PDF 預覽測試需要本機安裝 LibreOffice 的 `soffice`；若未安裝，該項測試會略過。應用程式本身透過 Docker 啟動時已包含 LibreOffice。

## API 概覽

- `GET /api/health`：健康檢查及上傳大小設定。
- `POST /api/uploads`：建立分片上傳。
- `GET /api/uploads/{upload_id}`：查詢已上傳分片。
- `PUT /api/uploads/{upload_id}/chunks/{index}`：傳送單一分片。
- `POST /api/uploads/{upload_id}/complete`：完成上傳並排入轉換。
- `GET /api/jobs/{job_id}` 與 `WS /api/jobs/{job_id}/ws`：查詢或訂閱進度。
- `GET /api/jobs/{job_id}/preview/pages/{page_number}`：取得從 **1** 開始計數的 PDF 頁面預覽 PNG。
- `GET /api/jobs/{job_id}/preview`：在瀏覽器內開啟 PDF。
- `GET /api/jobs/{job_id}/download`：下載 PDF。

## 部署與疑難排解

- **上傳被拒絕或顯示 413**：檢查檔案是否超過 20 MiB，以及前方是否另有反向代理設定了更小的請求上限。
- **動畫轉換失敗**：查看介面顯示的原投影片頁碼及 `docker compose logs worker`。目前僅支援上述點擊進入動畫；其他效果會明確報錯。
- **公式或符號外觀不同**：先檢查來源 PPTX 是否包含可用的公式備援圖片，並確認所需字型已合法安裝。以網站預覽逐頁核對結果。
- **容器啟動失敗**：執行 `docker compose ps` 和 `docker compose logs --tail=100`，並確認 `PORT` 未被其他程式占用、`DATA_PATH` 有足夠空間。

目前沒有帳號系統。若要公開部署，請在入口配置 HTTPS，並依使用場景加上存取控制、流量限制及監控。檔案由排程進行一般檔案刪除；這不等同於儲存裝置層級的安全抹除。

## 授權

專案程式碼採用 [MIT License](LICENSE)。LibreOffice、字型及其他依賴項各自遵循其授權條款。
