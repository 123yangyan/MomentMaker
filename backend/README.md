# MomentMaker 后端

## 1. 安装依赖

```powershell
cd backend
python -m pip install -r requirements.txt
```

## 2. 配置模型密钥

密钥只应配置在启动后端的终端中，不要写入前端或提交到代码仓库。

```powershell
$env:SILICONFLOW_API_KEY="你的硅基流动密钥"
$env:ARK_API_KEY="你的火山方舟密钥"

# 可选：账号开通的 Seedream 推理模型 ID
$env:ARK_IMAGE_MODEL="doubao-seedream-5-0-lite-260128"
```

## 3. 启动服务

必须在配置密钥的同一个 PowerShell 窗口中启动：

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

单端口访问（页面 + API 同一地址）：

- 广场首页：`http://127.0.0.1:8000/`
- 上传页：`http://127.0.0.1:8000/upload.html`
- 接口文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

## 3.1 公网分享（Cloudflare 临时隧道）

电脑需保持开机、联网。后端启动后，另开一个终端：

```powershell
winget install Cloudflare.cloudflared
cloudflared tunnel --url http://127.0.0.1:8000
```

终端会输出类似 `https://random-words.trycloudflare.com` 的 HTTPS 链接，可直接发给别人：

- 首页：`https://你的隧道域名/`
- 上传：`https://你的隧道域名/upload.html`

说明：

- 临时隧道每次重启域名会变，需重新发链接
- 用户无需账号，浏览器自动生成匿名身份即可上传
- 视频建议 MP4，尽量小于几十 MB（隧道对大文件较敏感）
- 不要把 API 密钥发给他人；演示时可不宣传 `/docs` 地址

## 4. 运行离线测试

测试会动态生成 6 张图片，并模拟两个第三方 API。上传、评分落库、排序选四张、生图转存、任务状态和调用日志均会运行，测试结束后自动清理数据。

```powershell
python -m unittest discover -s tests -v
```

## 任务状态

`pending → scoring → selecting → generating → downloading → succeeded`

- 上传 1～20 张图片均可创建任务
- 成功评分至少 1 张即可继续，自动选择最高 1～4 张参考图
- 无 P4 确认页，评分完成后直接生图

任何阶段出错都会进入 `failed`，并通过任务状态接口返回适合用户阅读的错误信息。

## 前端联调

两种方式任选其一：

**方式 A（推荐演示/公网）：** 只启动后端，直接访问 `http://127.0.0.1:8000/`。

**方式 B（开发热更新）：** 5173 端口单独开静态页，API 仍打 8000：

```powershell
cd prototype
python -m http.server 5173
```

`prototype/js/task-api.js` 会在 5173 下自动指向 `http://127.0.0.1:8000`，单端口或公网访问时使用当前页面域名。详见 `docs/INTEGRATION.md`。
