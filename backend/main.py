from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from config import BASE_DIR, CORS_ORIGINS, FILES_DIR, MOCK_DIR

# 原型页目录：与 backend 同级，便于单端口同时提供页面和 API。
PROTOTYPE_DIR = BASE_DIR.parent / "prototype"


class NoCacheStaticFiles(StaticFiles):
    """演示期间 HTML/JS/CSS 禁止浏览器缓存，避免用户看到旧版按钮或脚本。"""

    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        content_type = response.headers.get("content-type", "")
        if (
            path.endswith((".html", ".js", ".css"))
            or "text/html" in content_type
            or "javascript" in content_type
            or "text/css" in content_type
        ):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response
from database import (
    Base,
    engine,
    migrate_database,
    publish_completed_tasks,
    recover_stuck_tasks,
)
from routers import task, upload, works

# MVP 阶段直接自动建表；正式生产环境应改用 Alembic 数据库迁移。
Base.metadata.create_all(bind=engine)
migrate_database()
recover_stuck_tasks()
# 兼容旧数据：过去已经生成成功但仍显示“待发布”的作品自动补到广场。
publish_completed_tasks()

app = FastAPI(
    title="MomentMaker API",
    description="MomentMaker 文件上传、AI 任务和作品广场接口",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    # 本地联调地址；部署后通过环境变量配置正式前端域名。
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 先注册更具体的 Mock 路径，再注册通用文件路径。
app.mount("/files/mock", StaticFiles(directory=str(MOCK_DIR)), name="mock-files")
app.mount("/files", StaticFiles(directory=str(FILES_DIR)), name="files")

app.include_router(upload.router, prefix="/api")
app.include_router(task.router, prefix="/api")
app.include_router(works.router, prefix="/api")


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    """把 FastAPI 默认错误统一成前端约定的结构。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": str(exc.detail), "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"code": 422, "message": "请求参数格式错误", "data": exc.errors()},
    )


@app.get("/health")
def health():
    """部署平台和联调人员可用此接口判断后端是否存活。"""
    return {"code": 200, "message": "ok", "data": {"status": "healthy"}}


# 最后挂载原型页；html=True 使 / 自动返回 index.html，且必须放在 API 路由之后。
if PROTOTYPE_DIR.is_dir():
    app.mount(
        "/",
        NoCacheStaticFiles(directory=str(PROTOTYPE_DIR), html=True),
        name="prototype",
    )
