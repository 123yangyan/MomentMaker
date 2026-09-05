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
python -m uvicorn main:app --reload --port 8000
```

接口文档地址：`http://127.0.0.1:8000/docs`

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

原型页请用本地 HTTP 服务在 5173 端口打开：

```powershell
cd prototype
python -m http.server 5173
```

前端 API 基址默认为 `http://127.0.0.1:8000`，详见 `prototype/INTEGRATION.md`。
