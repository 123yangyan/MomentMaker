import os
from pathlib import Path

from dotenv import load_dotenv

# 后端目录作为统一基准，避免从不同工作目录启动时路径失效。
BASE_DIR = Path(__file__).resolve().parent
# 自动加载本地 .env；系统环境变量优先，不会被文件中的值覆盖。
load_dotenv(BASE_DIR / ".env")

FILES_DIR = BASE_DIR / "files"
UPLOAD_DIR = FILES_DIR / "uploads"
ELEMENTS_DIR = FILES_DIR / "elements"
RESULTS_DIR = FILES_DIR / "results"
MOCK_DIR = BASE_DIR / "mock"

MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 100 * 1024 * 1024
MAX_FILES = 20
MIN_REFERENCE_IMAGES = 1
MAX_REFERENCE_IMAGES = 4
TASK_TIMEOUT_SECONDS = 60

# 本地联调默认放行 5173；部署时可通过 CORS_ORIGINS 追加正式前端域名。
_default_cors = "http://localhost:5173,http://127.0.0.1:5173"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", _default_cors).split(",")
    if origin.strip()
]

# 两个第三方模型都只在后端读取密钥，绝不能把密钥返回给前端。
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "").strip()
ARK_API_KEY = os.environ.get("ARK_API_KEY", "").strip()
VL_MODEL = os.environ.get("VL_MODEL", "zai-org/GLM-4.5V").strip()
ARK_IMAGE_MODEL = os.environ.get(
    "ARK_IMAGE_MODEL", "doubao-seedream-5-0-lite-260128"
).strip()
AI_REQUEST_TIMEOUT_SECONDS = int(os.environ.get("AI_REQUEST_TIMEOUT_SECONDS", "180"))
AI_MAX_RETRIES = int(os.environ.get("AI_MAX_RETRIES", "2"))

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/heic", "image/heif"}
ALLOWED_VIDEO_TYPES = {"video/mp4"}

for directory in (UPLOAD_DIR, ELEMENTS_DIR, RESULTS_DIR, MOCK_DIR):
    directory.mkdir(parents=True, exist_ok=True)
