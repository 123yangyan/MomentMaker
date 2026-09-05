# MomentMaker MVP 联调接手说明

## 1. 当前结论

- 当前只有静态前端原型，尚未实现真实 API、FastAPI 后端和前后端联调。
- 本阶段只支持图片上传，不支持视频，不做视频校验、抽帧或视频字段。
- AI 主流程：多图评分 → 选出 3～4 张图片 → 生成成品图。
- 用户匿名使用，不收集姓名、手机号、微信号、邮箱、GPS、IMEI、MAC、IP 等隐私信息。
- `user_id` 由前端生成 UUID 并保存到 `localStorage`，请求时通过 `X-Session-Id` 传递。
- 只采集浏览器允许读取的非敏感设备信息；无法可靠获取的手机型号等字段传 `null`，不得伪造或做设备指纹。
- 作品名称必填，物料类型改为单选。
- 不提交伴随信息、图文信息或用户自由 `prompt`，因为当前 HTML 没有对应输入框。
- 每个文件计算 SHA-256；后端必须重新计算并比对，校验失败不得进入 AI 流程。

## 2. 唯一字段命名

后续代码、数据库、注释和接口示例统一使用以下名称，不再混用旧变量：

| 含义 | 统一名称 | 禁止继续使用 |
| --- | --- | --- |
| 匿名用户/会话 | `session_id` | `user_id` 作为后端会话主键 |
| 上传批次 | `upload_id` | — |
| 文件编号 | `file_id` | — |
| 作品名称 | `work_name` | `work_title`、`workName` |
| 模板类型 | `template` | `template_type` |
| 视觉风格 | `style` | `visual_style` |
| 单选物料 | `material` | `materials` |
| 故事地图枚举 | `map` | `story_map` |
| 明信片枚举 | `postcard` | `receipt`、`poster` |
| 任务编号 | `task_id` | — |

物料为单选，合法值只有 `badge`（吧唧）、`postcard`（明信片）、`keychain`（钥匙扣）。不得新增小票或海报物料。

## 3. 最终页面流程

```text
P1 广场
  → P2 上传图片、填写必填作品名称、选择单个物料
  → 创建任务
  → 后端对全部图片评分并选出 3～4 张
  → P4 展示入选图片，允许选择、取消、替换和排序
  → 调用最终合成接口
  → P5 预览成品、保存或发布到广场
```

P4 必须保留。不要执行原联调方案第 66 行提出的“废弃 `/compose` 与 `/elements/.../replace`”。P4 统一使用“候选图片”命名，不再使用“抠图元素”。

## 4. 接口路线

文档流程图和实际接口全部统一为复数：

```text
POST /api/uploads
POST /api/tasks
GET  /api/tasks/{task_id}
POST /api/tasks/{task_id}/selection
POST /api/tasks/{task_id}/compose
GET  /api/works
POST /api/works
POST /api/works/{work_id}/likes
```

所有响应采用 `{code, message, data}`。HTTP 状态码表达请求成败；`message` 面向用户；内部诊断只写后端日志或数据库。

## 5. 上传及标签示例

`POST /api/uploads` 使用 `multipart/form-data`：

```text
files: 1～20 张图片
client_manifest: JSON 字符串
X-Session-Id: 前端生成的 UUID
```

`client_manifest` 示例：

```json
{
  "schema_version": "1.0",
  "device": {
    "device_type": "mobile",
    "manufacturer": "Apple",
    "model": null,
    "operating_system": "iOS",
    "operating_system_version": "18.0",
    "browser": "WeChat",
    "browser_version": "8.0.52",
    "language": "zh-CN",
    "timezone": "Asia/Shanghai",
    "screen_width": 393,
    "screen_height": 852,
    "pixel_ratio": 3
  },
  "files": [
    {
      "client_file_id": "local_001",
      "filename": "photo.jpg",
      "size_bytes": 4194304,
      "mime_type": "image/jpeg",
      "sha256": "前端计算的 SHA-256"
    }
  ]
}
```

后端不得信任前端标签，必须重新检测 MIME、大小、宽高和 SHA-256。建议返回：

```json
{
  "code": 0,
  "message": "上传成功",
  "data": {
    "upload_id": "upl_001",
    "files": [
      {
        "file_id": "file_001",
        "filename": "photo.jpg",
        "mime_type": "image/jpeg",
        "size_bytes": 4194304,
        "width": 3024,
        "height": 4032,
        "sha256": "后端计算的 SHA-256",
        "integrity_verified": true,
        "preview_url": "/files/file_001/preview"
      }
    ]
  }
}
```

## 6. 创建任务示例

`POST /api/tasks` 使用 JSON：

```json
{
  "schema_version": "1.0",
  "upload_id": "upl_001",
  "file_ids": ["file_001", "file_002", "file_003", "file_004"],
  "work_name": "我的漫展记录",
  "template": "comic",
  "style": "anime",
  "material": "postcard"
}
```

规则：`work_name` 去除首尾空格后必须为 1～30 个字符；`material` 必须是单个字符串；图片少于 3 张时不创建生成任务。

返回 `task_id` 后，前端每 2 秒请求 `GET /api/tasks/{task_id}`。状态统一为：

```text
pending → scoring → selecting → awaiting_selection → generating → downloading → succeeded
任一步骤可进入 failed
```

评分成功图片达到 4 张时默认选前 4 张；只有 3 张时选择 3 张；少于 3 张时任务失败并返回用户可读原因。

## 7. P4 页面与接口示例

P4 展示评分后选出的 3～4 张图片、分数摘要和顺序。用户可以取消、重新加入候选图、拖拽排序，然后确认合成。

保存选择：

```http
POST /api/tasks/{task_id}/selection
```

```json
{
  "selected_file_ids": ["file_004", "file_002", "file_001"]
}
```

要求：必须属于当前 `session_id` 和当前任务；数量只能是 3 或 4；数组顺序就是合成顺序；不得重复。

确认合成：

```http
POST /api/tasks/{task_id}/compose
```

无需再次提交自由 Prompt。后端使用任务中已保存的模板、风格、物料和图片顺序生成成品图，并立即返回当前任务状态。

## 8. 模块边界

- 前端：生成匿名会话、读取非敏感设备信息、计算客户端哈希、上传图片、提交任务、展示P4、轮询和展示错误。
- 后端：重新检测文件、校验哈希和文件归属、保存数据库、维护状态机、调用AI模块、保存成品和发布作品。
- AI评分模块：逐图返回结构化评分；单图失败允许继续，不处理HTTP和数据库。
- AI生成模块：接收按顺序排列的3～4张本地图片及固定业务参数，返回成品文件；不得硬编码输入路径。

## 9. 现有前端后续修改点

- `upload.html` 保持吧唧、明信片、钥匙扣三种物料及单选交互，不增加其他物料。
- `app.js` 不再为空作品名写入默认值，改为阻止提交并提示。
- `app.js` 增加 SHA-256、上传、创建任务、2秒轮询和失败恢复。
- 新增或复用 P4 页面，不得从上传页直接跳回广场。
- P4 确认后调用复数路径的 selection/compose 接口，再进入 P5。
- 所有新增代码注释应解释“字段含义、来源、所有者和停止条件”，不要只复述代码。

## 10. 行号歧义

- 原方案第 66 行已明确放弃：不要废弃 selection/compose；P4 依赖这两个能力。
- 原方案第 16 行只是 YAML 中 `frontend-integration` 的 `status: pending`，不是业务功能。除非产品方另有说明，不应据此删除前端联调模块。
