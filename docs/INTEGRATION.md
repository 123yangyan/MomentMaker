# MomentMaker 联调说明（无 P4 自动生图版）

## 冻结契约

- 上传：1～20 张图片
- 评分：GLM-4.5V 对全部图片评分
- 选图：自动选择成功评分中最高 1～4 张
- 生图：Seedream 直接生成，无 P4 确认页
- 接口路径（单数）：
  - `POST /api/upload`
  - `POST /api/task/start`
  - `GET /api/task/{task_id}/status`
  - `GET /api/task/mine`
  - `POST /api/works`
  - `GET /api/works`
  - `GET /api/works/mine`
  - `POST /api/works/{work_id}/like`

## 本地启动

### 1. 后端

```powershell
cd backend
python -m pip install -r requirements.txt
copy .env.example .env
# 编辑 .env 填入 SILICONFLOW_API_KEY 和 ARK_API_KEY
python -m uvicorn main:app --reload --port 8000
```

### 2. 前端

```powershell
cd prototype
python -m http.server 5173
```

浏览器访问：`http://127.0.0.1:5173/upload.html`

## 页面流程

1. 上传页：选图 → 填作品名 → 选模板/物料 → 开始创作
2. 同页轮询：上传 / 评分 / 筛选 / 生图 / 保存
3. 成功后：预览海报、查看入选 1～4 张、发布到广场
4. 广场页：`GET /api/works` 动态加载
5. 我的页：按匿名 `X-Session-Id` 加载任务与作品

## 匿名会话

- 前端 `upload-labels.js` 生成 UUID 存 `localStorage`
- 所有受保护请求带请求头 `X-Session-Id`
