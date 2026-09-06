# MomentMaker 后端开发文档（杨洋）

**版本**：v1.2  
**更新日期**：2026-09-04  
**代码目录**：`backend/`

> 接口字段以 [API_CONTRACT_FREEZE.md](./API_CONTRACT_FREEZE.md) 为准。v1.2 新增 `story_text`、`work_title`、元素替换和作品详情接口。

## 1. 职责范围

杨洋负责以下后端能力：

1. 接收并保存用户上传的图片、视频。
2. 保存文件、生成任务和广场作品数据。
3. 调用杨帆提供的 Python AI 模块。
4. 向前端提供任务进度和处理结果。
5. 提供 Mock 演示模式，保证 AI 服务不可用时仍可演示。

不负责抠图、视频抽帧和图片合成算法本身，这三个部分由杨帆提供。

## 2. 当前完成情况

目前已经实现：

- FastAPI 服务和 Swagger 接口文档。
- SQLite 数据库及自动建表。
- 已有数据库的轻量字段迁移。
- 图片、视频批量上传。
- 文件类型、数量和大小校验。
- JPG、PNG、HEIC、HEIF、MP4 支持。
- 图片 EXIF 原始拍摄时间读取。
- 生成任务创建、进度查询和成品合成接口。
- 广场作品查询、发布和点赞接口。
- 统一错误响应。
- Mock 演示数据及静态素材。

真实抽帧、抠图和合成需要等待 AI 模块接入。

## 3. 技术栈

- Python 3.11 或更高版本
- FastAPI：HTTP API 框架
- Uvicorn：开发服务器
- SQLAlchemy 2：数据库操作
- SQLite：MVP 数据库
- aiofiles：异步保存上传文件
- Pillow：图片格式校验和 EXIF 读取
- pillow-heif：读取 iPhone HEIC/HEIF 图片
- python-multipart：处理表单文件上传

全部依赖记录在 `backend/requirements.txt`。

## 4. 目录结构

```text
backend/
├── main.py                 # FastAPI 入口、跨域、异常处理、静态文件
├── config.py               # 路径、文件大小和类型配置
├── database.py             # SQLite 连接、Session、轻量迁移
├── models.py               # files、tasks、works 三张表
├── schemas.py              # API 请求参数校验
├── requirements.txt        # Python 依赖
│
├── routers/
│   ├── upload.py           # 文件上传、图片拍摄时间读取
│   ├── task.py             # 任务创建、进度查询、最终合成
│   └── works.py            # 广场查询、发布、点赞
│
├── ai/
│   └── __init__.py         # AI 模块接入目录
│
├── mock/
│   ├── task_done.json      # Mock 任务结果
│   ├── works.json          # Mock 广场数据
│   └── *.svg               # Mock 图片素材
│
└── files/
    ├── uploads/            # 用户上传的原始素材
    ├── elements/           # AI 提取的透明元素图
    └── results/            # 最终生成的成品图
```

## 5. 安装与启动

### 5.1 安装依赖

在项目根目录执行：

```bash
cd backend
py -m pip install -r requirements.txt
```

### 5.2 启动服务

```bash
py -m uvicorn main:app --reload --port 8000
```

启动成功后可以访问：

- 服务首页：`http://localhost:8000/`
- 健康检查：`http://localhost:8000/health`
- Swagger 文档：`http://localhost:8000/docs`
- Mock 广场：`http://localhost:8000/api/works?demo=true`

`--reload` 表示代码修改后自动重启，仅用于开发环境。

## 6. 数据库设计

数据库文件为：

```text
backend/momentmaker.db
```

后端第一次启动时会自动创建数据库和数据表。

### 6.1 files：上传文件表

每成功上传一个文件，就新增一条记录。

- `id`：文件 UUID，主键。
- `filename`：用户上传时的原始文件名。
- `stored_path`：文件在服务器上的实际路径。
- `file_type`：`image` 或 `video`。
- `size`：文件大小，单位为字节。
- `image_created_at`：图片 EXIF 原始拍摄时间，可为空。
- `created_at`：文件上传到服务器的时间。

`image_created_at` 和 `created_at` 的含义不同：

```text
image_created_at = 用户拍摄照片的时间
created_at       = 用户把文件上传到本系统的时间
```

以下图片可能没有 `image_created_at`：

- 截图。
- 被微信等软件压缩过的图片。
- 编辑软件导出时删除了 EXIF 的图片。
- 图片本身没有写入拍摄时间。

这种情况下数据库保存 `NULL`，后端不会根据文件名或系统时间进行猜测。

### 6.2 tasks：生成任务表

用户选择模板并点击“开始生成”后创建。

- `id`：任务 UUID，主键。
- `status`：当前任务状态。
- `progress`：进度，范围 0～100。
- `file_ids`：本次任务使用的文件 ID，使用 JSON 字符串保存。
- `template`：模板类型。
- `style`：视觉风格。
- `material`：物料类型列表。
- `elements`：AI 提取出的元素列表。
- `result_url`：最终成品地址，可为空。
- `error_message`：任务失败原因，可为空。
- `created_at`：任务创建时间。

任务状态包括：

- `pending`：等待处理。
- `processing`：正在抽帧或抠图。
- `done`：元素提取完成，等待用户选择。
- `composing`：正在合成最终成品。
- `finished`：全部完成。
- `failed`：处理失败。

### 6.3 works：广场作品表

用户点击“发布至广场”后创建。

- `id`：作品 UUID，主键。
- `cover_url`：封面图片地址。
- `result_urls`：全部成品地址列表。
- `template`：作品使用的模板。
- `style`：作品使用的视觉风格。
- `material`：物料类型列表。
- `nickname`：发布者昵称。
- `likes`：点赞数。
- `created_at`：发布时间。

### 6.4 三张表的数据关系

```text
files（用户上传素材）
   │
   │ file_ids
   ▼
tasks（AI 处理任务）
   │
   │ task_id
   ▼
works（发布到广场的作品）
```

目前 MVP 没有用户登录系统，因此没有用户表。

## 7. 图片拍摄时间读取

上传图片后，`routers/upload.py` 会读取 EXIF 信息。

读取优先级：

1. `DateTimeOriginal`：照片原始拍摄时间。
2. `DateTimeDigitized`：照片数字化时间。
3. `DateTime`：图片修改时间。

标准 EXIF 时间：

```text
2026:09:03 18:30:00
```

接口转换后返回 ISO 格式：

```text
2026-09-03T18:30:00
```

该时间通常不包含时区，因此 MVP 按照片中记录的本地时间原样保存。

已有数据库中没有该字段时，服务启动会自动执行：

```sql
ALTER TABLE files ADD COLUMN image_created_at DATETIME;
```

迁移操作可以重复启动，不会重复添加字段。正式生产项目应改用 Alembic 管理数据库版本。

## 8. API 统一约定

### 8.1 基础地址

```text
http://localhost:8000/api
```

### 8.2 成功响应

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

### 8.3 错误响应

```json
{
  "code": 400,
  "message": "错误原因",
  "data": null
}
```

常见 HTTP 状态码：

- `200`：请求成功。
- `400`：参数或业务状态错误。
- `404`：资源不存在。
- `413`：上传文件过大。
- `422`：请求体格式不符合接口要求。
- `500`：AI 调用或服务器内部处理失败。

## 9. 文件上传接口

### 9.1 请求

```text
POST /api/upload
Content-Type: multipart/form-data
```

表单字段：

- `files`：文件列表，最多 20 个。
- `demo`：可选的演示模式开关。

限制：

- 单张图片最大 10MB。
- 单个视频最大 100MB。
- 图片支持 JPG、PNG、HEIC、HEIF。
- 视频支持 MP4。

后端采用 1MB 分块写入，不会把整个大视频一次性加载到内存。

### 9.2 成功响应

```json
{
  "code": 200,
  "message": "上传成功",
  "data": {
    "file_ids": ["44bd8e54-xxxx-xxxx-xxxx-xxxxxxxxxxxx"],
    "previews": [
      {
        "file_id": "44bd8e54-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "url": "/files/uploads/44bd8e54-xxxx.jpg",
        "type": "image",
        "image_created_at": "2026-09-03T18:30:00"
      }
    ]
  }
}
```

图片无 EXIF 时间时：

```json
{
  "image_created_at": null
}
```

## 10. 生成任务接口

### 10.1 创建任务

```text
POST /api/task/start
```

请求：

```json
{
  "file_ids": ["文件ID"],
  "template": "comic",
  "style": "anime",
  "material": "badge",
  "story_text": "可选，活动描述，最多 500 字"
}
```

允许值：

- `template`：`comic`、`map`、`album`。
- `style`：可省略，默认 `anime`；也支持 `cyber`、`realistic`。
- `material`：单选，支持 `keychain`、`badge`、`postcard`。

前端只传这些结构化业务字段，不传完整 AI 提示词。后端会根据模板、物料、
视觉风格和用户描述构建最终提示词，并通过 `prompt_version` 记录规则版本。

响应：

```json
{
  "code": 200,
  "message": "任务创建成功",
  "data": {
    "task_id": "任务ID",
    "status": "pending"
  }
}
```

接口会立即返回任务 ID，抽帧和抠图在后台线程中进行。

### 10.2 查询任务进度

```text
GET /api/task/{task_id}/status
```

前端建议每两秒请求一次。

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "任务ID",
    "status": "processing",
    "progress": 60,
    "elements": [],
    "result_url": null,
    "error_message": null
  }
}
```

任务失败时：

```json
{
  "status": "failed",
  "error_message": "具体失败原因"
}
```

### 10.3 合成最终成品

```text
POST /api/task/{task_id}/compose
```

请求：

```json
{
  "selected_elements": ["元素1", "元素2"],
  "element_order": ["元素1", "元素2"],
  "work_title": "热爱，就要大声一点！"
}
```

`element_order` 表示从下到上的叠放顺序，两个数组必须包含相同元素。

成功后返回：

```json
{
  "code": 200,
  "message": "合成成功",
  "data": {
    "task_id": "任务ID",
    "status": "finished",
    "result_url": "/files/results/任务ID.png",
    "result_urls": ["/files/results/任务ID.png"]
  }
}
```

### 10.4 替换元素

```text
POST /api/task/{task_id}/elements/{element_id}/replace
```

请求：

```json
{
  "file_id": "重新上传后获得的文件ID"
}
```

任务状态必须为 `done`。后端对新图片重新抠图，并更新 `elements` 数组中对应项。

## 11. 广场作品接口

### 11.1 获取作品列表

```text
GET /api/works?page=1&page_size=12
```

- `page` 最小为 1。
- `page_size` 范围为 1～50。
- 作品按发布时间倒序返回。
- 列表项包含 `title` 字段。

### 11.2 获取作品详情

```text
GET /api/works/{work_id}
```

返回标题、全部成品图、模板、风格、物料、昵称、点赞和发布时间。分享链接 `/?work={work_id}` 依赖此接口。

Demo：`GET /api/works/demo-work-001?demo=true`

### 11.3 发布作品

```text
POST /api/works
```

请求：

```json
{
  "task_id": "已完成的任务ID",
  "nickname": "测试用户",
  "material": ["badge"]
}
```

只有状态为 `finished` 且存在结果图片的任务才能发布。作品标题取自任务合成时保存的 `work_title`。

### 11.4 点赞作品

```text
POST /api/works/{work_id}/like
```

MVP 暂时没有登录和防重复点赞，同一个用户可以多次调用。

## 12. 静态文件访问

文件保存后，通过以下 URL 访问：

```text
/files/uploads/文件名
/files/elements/文件名
/files/results/文件名
/files/mock/文件名
```

数据库保存相对 URL，前端根据后端域名进行拼接。

例如：

```text
http://localhost:8000/files/mock/result.svg
```

## 13. Mock 演示模式

核心接口支持 `demo=true`。

示例：

```text
GET /api/works?demo=true
POST /api/task/start?demo=true
GET /api/task/demo-task-001/status
POST /api/task/demo-task-001/compose
POST /api/works?demo=true
```

Mock 模式的特点：

- 不调用 AI 模块。
- 不写入真实任务和作品数据。
- 返回固定演示素材。
- 用于断网、AI 异常或现场快速演示。

需要注意：Swagger 仍会根据接口定义要求填写请求体或选择上传文件，然后后端才会进入 Mock 分支。

## 14. AI 模块接入约定

杨帆需要把以下文件放入 `backend/ai/`：

```text
ai/
├── remove_bg.py
├── extract_frames.py
└── compose.py
```

### 14.1 抠图函数

```python
def remove_background(input_path: str, output_path: str) -> bool:
    """读取原图，输出透明 PNG；成功返回 True。"""
```

### 14.2 视频抽帧函数

```python
def extract_key_frames(
    video_path: str,
    output_dir: str,
    max_frames: int = 20
) -> list[str]:
    """返回抽取出的图片文件路径列表。"""
```

### 14.3 图片合成函数

```python
def compose_image(
    elements: list[dict],
    template: str,
    style: str,
    output_path: str
) -> bool:
    """生成最终图片；成功返回 True。"""
```

AI 文件未接入时，真实任务会进入 `failed`，并通过 `error_message` 返回原因，不会伪造不存在的结果图片。

## 15. 联调流程

前端和后端建议按照以下顺序联调：

```text
1. POST /api/upload
   前端保存 file_ids

2. POST /api/task/start
   前端把 file_ids、模板和风格传给后端

3. GET /api/task/{task_id}/status
   前端每两秒查询一次

4. status=done
   前端显示 elements，用户选择和排序

5. POST /api/task/{task_id}/compose
   后端返回 result_url

6. POST /api/works
   把结果发布到广场

7. GET /api/works
   广场显示最新作品
```

## 16. 测试方法

### 16.1 使用 Swagger

打开：

```text
http://localhost:8000/docs
```

选择接口后点击：

```text
Try it out → 填写参数 → Execute
```

### 16.2 建议测试内容

正常情况：

- 上传包含 EXIF 时间的 JPG。
- 上传不包含 EXIF 的 PNG。
- 上传 HEIC 图片。
- 上传 MP4 视频。
- 使用 Mock 模式走完整流程。

错误情况：

- 上传 TXT 文件。
- 上传损坏但伪装成 JPG 的文件。
- 一次上传超过 20 个文件。
- 图片超过 10MB。
- 查询不存在的任务。
- 使用错误的模板名称。
- 任务未完成时直接合成。
- 发布未完成的任务。

### 16.3 查看数据库

可以安装 Cursor/VS Code 的 SQLite Viewer 扩展，然后打开：

```text
backend/momentmaker.db
```

即可查看 `files`、`tasks`、`works` 的字段和实际数据。

## 17. 当前限制

1. AI 三个模块尚未接入，真实生成流程会失败，Mock 流程可正常演示。
2. `BackgroundTasks` 适合黑客松 MVP，不适合大量并发任务。
3. SQLite 适合单机演示，不适合多服务器并发写入。
4. 图片 EXIF 时间通常没有时区。
5. 没有登录系统和用户表。
6. 点赞没有防重复机制。
7. 上传文件目前保存在本机磁盘，部署到无持久化磁盘的平台时需要改用对象存储。

## 18. 后续升级建议

完成 MVP 后可以逐步升级：

1. 使用 Alembic 管理数据库迁移。
2. 使用 PostgreSQL 替换 SQLite。
3. 使用 Redis + Celery/RQ 处理 AI 异步任务。
4. 使用对象存储保存图片和视频。
5. 为 EXIF 时间增加时区字段。
6. 增加登录、用户作品和点赞记录表。
7. 增加自动化接口测试和并发压力测试。
