# Slides Bloom

[English](README.md) · [繁體中文](README.zh-TW.md) · **简体中文**

## 直接在线使用

打开 **[Slides Bloom 在线版](https://slidesbloom.duckdns.org/)**，即可在浏览器上传 PowerPoint（`.pptx`）、将点击动画转换为逐页 PDF、预览并下载结果。网站免费使用，无需安装软件或注册账号。

**将 PPTX 的点击动画展开为可以逐页阅读的 PDF。** Slides Bloom 是免费、开源、可自行部署的工具。上传演示文稿后，它会按照原始动画顺序生成每次点击后的累积画面，让讲义或分享用 PDF 保留讲述节奏。

## 转换结果是什么样子？

假设一张幻灯片中的 ①、②、③ 依次出现，输出的 PDF 会有四页：

![一张幻灯片的三次点击依次展开为四页 PDF，已经出现的项目会保留](docs/images/animation-steps.svg)

```text
第 1 页  原始起始画面，尚未点击
第 2 页  起始画面 + ①
第 3 页  起始画面 + ① + ②
第 4 页  起始画面 + ① + ② + ③
```

没有支持动画的静态幻灯片仍输出一页。同一次点击中同步或接续发生的进入效果会合并为同一 PDF 页。展开后的页面保持原始幻灯片顺序。

## 主要功能

- 上传最大 **20 MiB**（界面标为 20 MB）的 `.pptx`；以 8 MiB 分片传输，网络中断后重新选择同一文件即可续传。
- 后台异步分析动画并用 LibreOffice Impress 生成 PDF；界面显示上传和转换进度。
- 完成后可以在站内**逐页预览 PDF**，也可以在新标签页打开完整 PDF 或直接下载。
- 界面支持 English、繁體中文、简体中文；首次打开默认英文，浏览器会记住语言选择。
- 上传文件与生成的 PDF 在任务创建满 24 小时后，由每小时运行的清理任务移除。

## 技术栈

- **前端：** Next.js 15、React 19、TypeScript 和 CSS。界面构建为静态网站。
- **API 与文档处理：** Python 3.12 和 FastAPI 负责上传、任务状态及 PDF 预览；`lxml` 读取和修改 PPTX 动画数据，LibreOffice Impress 将展开后的幻灯片渲染为 PDF，`pypdf` 和 `pypdfium2` 用于 PDF 处理与预览。
- **后台任务与存储：** Celery 负责转换和定时清理；Redis 保存任务队列和进度。上传文件及 PDF 暂存于配置的数据目录，到期后清理。

## 快速启动

需要 Docker、Docker Compose，以及足够的可用内存和磁盘空间。Worker 的内存上限为 6 GB；建议为 Docker 提供超过 6 GB 的可用内存。解压和渲染所需空间可能远大于原始 PPTX，请将数据目录放在空间充足的本地 SSD 上。

在项目根目录执行：

```sh
cp -n .env.example .env
docker compose up --build -d
```

打开 [http://localhost:8080](http://localhost:8080)。如需更改对外端口或数据位置，请先编辑 `.env`：

```dotenv
PORT=8080
DATA_PATH=./data
```

`DATA_PATH` 存放上传分片、源文件和 PDF。`docker compose down` 会停止服务，但不会删除该目录中尚未过期的文件。自动清理需要 `beat` 服务持续运行。

### 确认服务正常

```sh
docker compose ps
curl http://localhost:8080/api/health
```

然后在页面上传一份含有点击进入动画的 PPTX。如果一张幻灯片有三次点击，预览中应看到起始画面及三个累积状态，共四页。需要查看处理记录时，可执行 `docker compose logs -f worker`。

## 系统组成

![从 PPTX 分片上传，经过 FastAPI、Celery 与 Redis、LibreOffice，到 PDF 预览与下载的处理流程](docs/images/conversion-flow.svg)

- **Next.js**：将上传、进度、语言切换、PDF 预览及下载界面构建为静态文件，由 Nginx 提供；正式环境不常驻运行 Node.js 服务。
- **Nginx / FastAPI**：网站与 API 入口、分片接收、文件验证、任务查询及预览图片。
- **Celery / Redis**：后台转换和进度通知。Worker 默认一次处理 1 个任务，容器内存上限为 6 GB，单个任务最长 2 小时；后续上传会排队。
- **Celery Beat**：每小时清理创建时间已超过 24 小时的任务文件。

Nginx 的单次请求体上限为 20 MiB；每个上传分片都小于此限制。上传时还会检查 PPTX 格式及解压后的安全上限。因此，20 MiB 是**文件上传上限**，并不保证每个这种大小的文件都能在特定机器的内存和磁盘容量下完成转换。

## 本地开发与测试

最简单的方式是先按上述 Compose 指令启动全部服务。如需在本机运行前端开发服务器：

```sh
cd frontend
npm ci
NEXT_PUBLIC_API_BASE=http://localhost:8080 npm run dev
```

开发页面位于 [http://localhost:3000](http://localhost:3000)，API 仍由 Compose 的 `localhost:8080` 提供。在 `frontend/` 中运行 `npm run build` 可以构建前端。

在项目根目录执行后端测试：

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -v
```

测试覆盖 20 MiB 限制、动画累积页面、公式图片遮罩，以及不支持动画的错误处理。完整的上传到 PDF 预览测试需要在本机安装 LibreOffice 的 `soffice`；如未安装，该项测试会跳过。通过 Docker 启动应用时，镜像已包含 LibreOffice。

## API 概览

- `GET /api/health`：健康检查和上传大小上限。
- `POST /api/uploads`：创建分片上传。
- `GET /api/uploads/{upload_id}`：查询已上传的分片。
- `PUT /api/uploads/{upload_id}/chunks/{index}`：上传单个分片。
- `POST /api/uploads/{upload_id}/complete`：完成上传并提交转换任务。
- `GET /api/jobs/{job_id}` 和 `WS /api/jobs/{job_id}/ws`：查询或订阅进度。
- `GET /api/jobs/{job_id}/preview/pages/{page_number}`：将 PDF 页面渲染为 PNG，页码从 **1** 开始。
- `GET /api/jobs/{job_id}/preview`：在浏览器中打开 PDF。
- `GET /api/jobs/{job_id}/download`：下载 PDF。

## 部署与故障排查

- **上传被拒绝或显示 413**：检查文件是否超过 20 MiB，以及前方是否还有请求体限制更低的反向代理。
- **动画转换失败**：查看界面提示的原始幻灯片页码和 `docker compose logs worker`。目前只支持上述点击进入动画。
- **公式或符号外观不同**：检查 PPTX 中是否有可用的公式备用图片，并在有授权的前提下安装所需字体。逐页预览 PDF 结果。
- **容器无法启动**：执行 `docker compose ps` 和 `docker compose logs --tail=100`，检查 `PORT` 是否被占用、`DATA_PATH` 是否有足够空间。

目前没有账号系统。公开部署前，请在入口配置 HTTPS，并根据使用场景增加访问控制、流量限制和监控。定时删除文件属于普通文件删除，不等同于存储设备级别的安全擦除。

## 许可证

项目代码采用 [MIT License](LICENSE)。LibreOffice、字体和其他依赖项分别遵循各自的授权条款。
