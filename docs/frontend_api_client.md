# 前端请求封装清单（连胜）

**版本**：v1.0  
**对照文档**：`docs/backend_yangyang.md`  
**建议文件**：前端项目里新建 `js/api.js`（或 `src/api/index.js`）

> 用法：页面只调用下面这些函数，不要在每个 HTML 里手写 `fetch`。  
> 演示：`sessionStorage.momentmaker_demo === '1'` 时，所有请求自动带 `demo=true`。

---

## 1. 建议先写的公共层

### 1.1 常量

```js
const API_BASE = 'http://localhost:8000'; // 上线后改成真实域名
const API = API_BASE + '/api';
```

图片地址是相对路径，统一用这个函数拼完整 URL：

```js
function fileUrl(path) {
  if (!path) return '';
  if (path.startsWith('http')) return path;
  return API_BASE + path; // 例如 /files/uploads/xxx.jpg
}
```

### 1.2 跨页状态（sessionStorage 键名）

| 键名 | 谁写入 | 谁读取 | 内容 |
|------|--------|--------|------|
| `momentmaker_demo` | 点「样例素材」时写成 `'1'` | 所有请求 | 演示开关 |
| `momentmaker_file_ids` | 上传成功 | 开始生成 | `string[]` JSON |
| `momentmaker_story_text` | 上传页点下一步 | 开始生成 | 最多 500 字 |
| `momentmaker_template` | 上传页 | 发布 | `comic` / `map` / `album` |
| `momentmaker_style` | 上传页 | 展示用 | 可选，默认 `anime` |
| `momentmaker_material` | 上传页 | 开始生成、发布 | `badge` 这类单个字符串 |
| `momentmaker_task_id` | 开始生成成功 | 编辑页、合成、发布 | 任务 UUID |
| `momentmaker_work_title` | 编辑页输入框 | 合成 | 最多 30 字 |
| `momentmaker_nickname` | 「我的」或发布弹窗 | 发布 | 最多 20 字，默认 `访客用户` |
| `momentmaker_result_url` | 合成成功 | 预览、下载 | 相对路径 |
| `momentmaker_my_work_ids` | 发布成功后追加 | 「我的」页（可选） | 自己发过的 `work_id` 列表 |

### 1.3 枚举对照（页面中文 → 接口英文）

模板类型：

| 页面文案 | 传给后端 |
|----------|----------|
| 连环画 | `comic` |
| 故事地图 | `map` |
| 记录册 | `album` |

视觉风格：

| 页面文案 | 传给后端 |
|----------|----------|
| 二次元 | `anime` |
| 演唱会/赛博 | `cyber` |
| 普通写实 | `realistic` |

物料（单选）：

| 页面文案 | 传给后端 |
|----------|----------|
| 钥匙扣 | `keychain` |
| 吧唧 | `badge` |
| 明信片 | `postcard` |

### 1.4 统一请求函数（建议只写这一个）

```js
async function request(path, options = {}) {
  const demo = sessionStorage.getItem('momentmaker_demo') === '1';
  const url = new URL(API + path, API_BASE);
  if (demo) url.searchParams.set('demo', 'true');

  const res = await fetch(url, options);
  const json = await res.json(); // 后端统一 { code, message, data }

  if (!res.ok || json.code !== 200) {
    throw new Error(json.message || '请求失败');
  }
  return json.data;
}
```

失败时页面要做的事（统一，不要每个接口各写一套）：

1. `showToast(error.message)`
2. 上传/生成失败：弹出「是否改用演示数据继续？」
3. 用户同意后：`sessionStorage.setItem('momentmaker_demo', '1')`，再重试同一个函数

可选探活（进首页时调一次）：

```js
async function pingHealth() {
  const res = await fetch(API_BASE + '/health');
  return res.ok;
}
```

不作为业务接口，只用来决定要不要默认开演示模式。

---

## 2. 必须封装的业务函数

按用户操作顺序排列。每个函数写清：**何时调用、参数、返回、存哪、失败怎么办**。

---

### 2.1 `uploadFiles(fileList)`

- **页面**：`upload.html` 点「下一步」，或编辑页「替换元素」先上传新图
- **方法**：`POST /api/upload`
- **Content-Type**：不要手动设。用 `FormData`，浏览器会自动带 `multipart/form-data`
- **表单字段名**：必须是 `files`（复数）

```js
async function uploadFiles(fileList) {
  const form = new FormData();
  Array.from(fileList).forEach((file) => form.append('files', file));
  return request('/upload', { method: 'POST', body: form });
}
```

**返回 `data`：**

```js
{
  file_ids: ['uuid', ...],
  previews: [
    { file_id, url, type: 'image'|'video', image_created_at: '2026-09-03T18:30:00'|null }
  ]
}
```

**成功后存储：**

- `momentmaker_file_ids` ← `data.file_ids`
- 预览图用 `fileUrl(item.url)` 显示

**前端先校验再请求：**

- 总数 ≤ 20
- 图片 ≤ 10MB，视频 ≤ 100MB
- 扩展名：jpg / jpeg / png / heic / heif / mp4

**失败：** 提示「网络不稳定，请重试」；可引导走样例素材（打开 demo 开关后重试，或跳过本步直接 `startTask` 带 demo）。

---

### 2.2 `startTask({ fileIds, template, material, storyText, style })`

- **页面**：`upload.html` 点「开始创作」
- **方法**：`POST /api/task/start`
- **按钮**：立刻禁用，文案改成「生成中...」，防止连点

```js
async function startTask(payload) {
  return request('/task/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_ids: payload.fileIds,          // 从 sessionStorage 读
      template: payload.template,         // comic | map | album
      material: payload.material,         // 单选，如 badge
      style: payload.style || 'anime',     // 可省略，后端也默认 anime
      story_text: payload.storyText || null, // 可空，最多 500 字
    }),
  });
}
```

**返回 `data`：** `{ task_id, status: 'pending' }`

**成功后存储：**

- `momentmaker_task_id`
- `momentmaker_template` / `style` / `material`

然后跳转 `editor.html`。真正抠图在后台跑，不要等它完成再跳。

---

### 2.3 `getTaskStatus(taskId)`

- **页面**：`editor.html` 进入后立刻开始轮询
- **方法**：`GET /api/task/{task_id}/status`
- **频率**：每 2000ms 一次；`done` / `finished` / `failed` 后立刻 `clearInterval`

```js
async function getTaskStatus(taskId) {
  return request(`/task/${taskId}/status`);
}
```

**返回 `data`：**

```js
{
  task_id,
  status,          // pending | processing | done | composing | finished | failed
  progress,        // 0~100，用来画进度条
  elements: [      // status=done 之后才有内容
    { id, url, label }
  ],
  result_url,      // 合成完成后才有
  error_message    // failed 时才有
}
```

**页面怎么用：**

| `status` | 前端做什么 |
|----------|------------|
| `pending` / `processing` | 继续 Loading，进度条 = `progress` |
| `done` | 停轮询，用 `elements` 渲染元素池；图片 `fileUrl(el.url)` |
| `composing` | 显示「正在合成成品」 |
| `finished` | 停轮询，展示 `result_url` |
| `failed` | 停轮询，提示 `error_message`，提供「用演示数据继续」 |

建议再包一层轮询，页面只关心回调：

```js
function pollTaskStatus(taskId, { onProgress, onDone, onFailed }) {
  const timer = setInterval(async () => {
    try {
      const data = await getTaskStatus(taskId);
      onProgress(data);
      if (data.status === 'done' || data.status === 'finished') {
        clearInterval(timer);
        onDone(data);
      }
      if (data.status === 'failed') {
        clearInterval(timer);
        onFailed(data);
      }
    } catch (err) {
      clearInterval(timer);
      onFailed({ error_message: err.message });
    }
  }, 2000);
  return () => clearInterval(timer); // 离开页面时调用，避免泄漏
}
```

超时（PRD：60 秒）：超时后提示，并建议切 demo 重试。

---

### 2.4 `replaceElement(taskId, elementId, fileId)`

- **页面**：编辑页某张元素点「替换」
- **前置**：新图先走 `uploadFiles([file])`，取出 `file_ids[0]`
- **方法**：`POST /api/task/{task_id}/elements/{element_id}/replace`
- **时机**：仅当任务 `status === 'done'`

```js
async function replaceElement(taskId, elementId, fileId) {
  return request(`/task/${taskId}/elements/${elementId}/replace`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_id: fileId }),
  });
}
```

**返回 `data`：** `{ element, elements }`  
用整份 `elements` 重新渲染元素池，不要只改 DOM 一张图（避免漏改 id/url）。

---

### 2.5 `composeTask(taskId, { selectedIds, orderIds, workTitle })`

- **页面**：编辑页确认元素后（建议独立「生成成品」按钮，不要和发布绑死）
- **方法**：`POST /api/task/{task_id}/compose`

```js
async function composeTask(taskId, payload) {
  return request(`/task/${taskId}/compose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      selected_elements: payload.selectedIds, // 选中的元素 id
      element_order: payload.orderIds,        // 从下到上的叠放顺序
      work_title: payload.workTitle,          // 1~30 字
    }),
  });
}
```

**硬规则：** `selected_elements` 和 `element_order` 必须是同一组 id，只是顺序可能不同。  
前端在发出前自己检查一遍，否则后端会 400。

**返回 `data`：** `{ task_id, status: 'finished', result_url, result_urls }`

**成功后存储：** `momentmaker_result_url`、`momentmaker_work_title`  
预览/下载用 `fileUrl(result_url)`。多页成品用 `result_urls` 做左右翻页。

---

### 2.6 `publishWork({ taskId, nickname, material })`

- **页面**：合成成功后再点「发布至广场」
- **方法**：`POST /api/works`
- **前提：** 任务必须已是 `finished` 且有结果图

```js
async function publishWork(payload) {
  return request('/works', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      task_id: payload.taskId,
      nickname: payload.nickname || '访客用户', // 1~20 字
      material: payload.material,              // 与选模板时同一份
    }),
  });
}
```

**返回 `data`：** `{ work_id, share_url, cover_url }`

**成功后：**

- 「复制链接」复制：`location.origin + data.share_url`（例如 `https://xxx/?work=uuid`）
- 可选：把 `work_id` 推进 `momentmaker_my_work_ids`（「我的」页用，后端没有登录接口）
- 弹窗展示成功，再回广场

作品标题**不用在发布接口再传**，后端会用合成时的 `work_title`。

---

### 2.7 `getWorks(page = 1, pageSize = 12)`

- **页面**：`index.html` 打开时
- **方法**：`GET /api/works?page=&page_size=`

```js
async function getWorks(page = 1, pageSize = 12) {
  return request(`/works?page=${page}&page_size=${pageSize}`);
}
```

**返回 `data`：**

```js
{
  total, page, page_size,
  items: [
    { work_id, title, cover_url, template, style, material, nickname, likes, created_at }
  ]
}
```

卡片渲染：

- 封面：`fileUrl(item.cover_url)`
- 标题：`item.title`
- 作者：`item.nickname`
- 点赞：`item.likes`
- 卡片 `data-work-id = item.work_id`，点击后调详情

瀑布流可先渲染 6 张（PRD 首屏），其余懒加载。

---

### 2.8 `getWorkDetail(workId)`

- **页面**：点卡片打开 Lightbox；或 URL 带 `?work=`
- **方法**：`GET /api/works/{work_id}`

```js
async function getWorkDetail(workId) {
  return request(`/works/${workId}`);
}
```

**返回 `data`：**

```js
{
  work_id, title, cover_url, result_urls,
  template, style, material, nickname, likes, created_at
}
```

Lightbox 主图用 `result_urls[0]`（没有则用 `cover_url`）。  
分享进入：`const workId = new URLSearchParams(location.search).get('work')`，有值就调这个接口并打开 Lightbox。

演示详情：`GET /api/works/demo-work-001?demo=true`（`request()` 会自动加 demo）。

---

### 2.9 `likeWork(workId)`

- **页面**：Lightbox 里点爱心
- **方法**：`POST /api/works/{work_id}/like`
- **注意：** MVP 没有登录，也没有取消点赞。前端可以做「点过变红」，但再点不要再请求（避免数字狂涨）。不要做取消点赞接口，后端没有。

```js
async function likeWork(workId) {
  return request(`/works/${workId}/like`, { method: 'POST' });
}
```

**返回 `data`：** `{ likes: 89 }`  
用这个数字覆盖页面，不要自己 +1（避免和服务器不一致）。

---

## 3. 不要封装成后端请求的功能

这些继续留在前端本地即可：

| 功能 | 做法 |
|------|------|
| 保存草稿 | `localStorage.momentmaker_draft` |
| 「我的」草稿列表 | 读上面的草稿 |
| 「我的」已发布 | 读 `momentmaker_my_work_ids`，再调 `getWorkDetail`；没有就显示空 |
| 顶部轮播 / 队员介绍 | 静态 HTML 或本地 JSON |
| 模板预览缩略图 | 美术静态图，按 `template + style` 本地映射 |
| 保存到本地 | `<a download>` 指向 `fileUrl(result_url)`，或 `fetch` 图片再触发下载 |
| 作品名称默认「用户ABCD」 | 已有 `sessionStorage`，合成时作为 `work_title` 传出 |

---

## 4. 页面 × 函数对照（写代码时贴在旁边）

| 页面 | 进入时 | 主按钮 | 还可能调 |
|------|--------|--------|----------|
| `index.html` | `getWorks()`；若 URL 有 `work` 再 `getWorkDetail()` | 卡片 → 详情 | `likeWork()` |
| `upload.html` | 无 | 「下一步」→ `uploadFiles()` | 样例：打开 demo 后同样上传或跳过 |
| `template.html` | 检查已有 `file_ids` | 「开始生成」→ `startTask()` | 无 |
| `editor.html` | `pollTaskStatus(taskId)` | 选完元素 → `composeTask()` → `publishWork()` | `uploadFiles` + `replaceElement` |
| `mine.html` | 可选：遍历本地 `work_id` 调详情 | 无必须接口 | 样例入口只开 demo 开关 |

建议的创作时序（和后端第 15 节一致）：

```text
uploadFiles
  → startTask
    → pollTaskStatus 直到 done
      → （可选）replaceElement
        → composeTask
          → publishWork
            → getWorks
```

---

## 5. 错误码怎么提示用户

| HTTP / 场景 | 用户文案建议 |
|-------------|--------------|
| 400 | 直接显示后端 `message`（参数错、任务未完成就合成等） |
| 404 | 「找不到这个作品/任务」 |
| 413 | 「文件太大了，图片不超过 10MB，视频不超过 100MB」 |
| 422 | 「提交格式不对，请返回上一步检查」 |
| 500 | 「生成服务忙，是否改用演示数据？」 |
| 网络失败 / 超时 | 「网络不稳定，请重试或使用样例素材」 |

---

## 6. 最小可跑通的调用示例（方便自测）

在浏览器控制台按顺序执行（后端已启动、`demo` 打开时最稳）：

```js
sessionStorage.setItem('momentmaker_demo', '1');

const task = await startTask({
  fileIds: ['demo'],           // demo 模式下后端仍可能要求请求体，以 Swagger 为准
  template: 'comic',
  style: 'anime',
  material: 'badge',
  storyText: '黑客松现场',
});

const status = await getTaskStatus(task.task_id);
const composed = await composeTask(task.task_id, {
  selectedIds: status.elements.map((e) => e.id),
  orderIds: status.elements.map((e) => e.id),
  workTitle: '热爱，就要大声一点！',
});
const published = await publishWork({
  taskId: task.task_id,
  nickname: '访客用户',
  material: ['badge'],
});
const list = await getWorks();
```

真实联调把 `fileIds` 换成 `uploadFiles` 的返回值，并去掉 demo 开关。

---

## 7. 实现时注意这 5 件事

1. **跨域**：后端已开 CORS；本地前端不要用 `file://` 打开页面，用 Live Server / 静态服务器。
2. **demo 要全程一致**：中途不要有的请求带 `demo`、有的不带。
3. **模板和物料直接传英文枚举**：例如 `map`、`postcard`；不要传页面中文。
4. **轮询离开页面要清定时器**，否则用户返回广场后还在打任务接口。
5. **AI 未接入时真实任务会 `failed`**，评委演示请默认走 `demo=true`。
