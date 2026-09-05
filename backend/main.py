from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import FILES_DIR, MOCK_DIR
from database import Base, engine, migrate_database
from routers import task, upload, works

# MVP 阶段直接自动建表；正式生产环境应改用 Alembic 数据库迁移。
Base.metadata.create_all(bind=engine)
migrate_database()

app = FastAPI(
    title="MomentMaker API",
    description="MomentMaker 文件上传、AI 任务和作品广场接口",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    # 本地联调地址；部署后通过环境变量配置正式前端域名。
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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


@app.get("/")
def root():
    return {"code": 200, "message": "MomentMaker API is running!", "data": None}


@app.get("/health")
def health():
    """部署平台和联调人员可用此接口判断后端是否存活。"""
    return {"code": 200, "message": "ok", "data": {"status": "healthy"}}
