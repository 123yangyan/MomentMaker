import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener
from sqlalchemy.orm import Session

from config import (
    ALLOWED_IMAGE_TYPES,
    ALLOWED_VIDEO_TYPES,
    MAX_FILES,
    MAX_IMAGE_SIZE,
    MAX_VIDEO_SIZE,
    UPLOAD_DIR,
)
from database import get_db
from models import FileRecord

router = APIRouter(tags=["文件上传"])

# 让 Pillow 能读取 iPhone 常见的 HEIC/HEIF 图片。
register_heif_opener()


def inspect_image(image_path: Path) -> tuple[datetime | None, int, int]:
    """
    读取图片 EXIF 中的原始拍摄时间。

    优先顺序：DateTimeOriginal（拍摄）→ DateTimeDigitized（数字化）
    → DateTime（图片修改）。图片没有这些元数据时返回 None。
    """
    # Pillow 要求 verify() 紧跟 open()；校验后对象不可继续读取，因此再打开一次。
    with Image.open(image_path) as image:
        image.verify()

    with Image.open(image_path) as image:
        width, height = image.size
        exif = image.getexif()
        raw_time = exif.get(36867) or exif.get(36868) or exif.get(306)

    if not raw_time:
        return None, width, height
    if isinstance(raw_time, bytes):
        raw_time = raw_time.decode("utf-8", errors="ignore")

    try:
        created_at = datetime.strptime(
            str(raw_time).strip()[:19], "%Y:%m:%d %H:%M:%S"
        )
        return created_at, width, height
    except ValueError:
        # 某些设备写入非标准时间格式，此时保留为空，不能错误猜测。
        return None, width, height


@router.post("/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    demo: bool = False,
    x_session_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """校验并保存用户上传的图片或视频。"""
    try:
        # 首次请求可不传，由后端生成后返回；后续请求应复用同一个 UUID。
        session_id = str(uuid.UUID(x_session_id)) if x_session_id else str(uuid.uuid4())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Session-Id 必须是有效 UUID") from exc

    if demo:
        return {
            "code": 200,
            "message": "上传成功（演示模式）",
            "data": {
                "file_ids": ["demo-img-1", "demo-img-2"],
                "previews": [
                    {
                        "file_id": "demo-img-1",
                        "url": "/files/mock/demo1.svg",
                        "type": "image",
                        "image_created_at": "2026-09-03T18:30:00",
                    },
                    {
                        "file_id": "demo-img-2",
                        "url": "/files/mock/demo2.svg",
                        "type": "image",
                        "image_created_at": "2026-09-03T19:15:00",
                    },
                ],
            },
        }

    if not files or len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"一次最多上传 {MAX_FILES} 个文件")

    previews: list[dict] = []
    saved_paths: list[Path] = []

    try:
        for file in files:
            content_type = (file.content_type or "").lower()
            if content_type in ALLOWED_IMAGE_TYPES:
                file_type, max_size = "image", MAX_IMAGE_SIZE
            elif content_type in ALLOWED_VIDEO_TYPES:
                file_type, max_size = "video", MAX_VIDEO_SIZE
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持文件 {file.filename} 的格式",
                )

            file_id = str(uuid.uuid4())
            suffix = Path(file.filename or "").suffix.lower()
            if not suffix:
                suffix = ".mp4" if file_type == "video" else ".jpg"
            stored_path = UPLOAD_DIR / f"{file_id}{suffix}"
            saved_paths.append(stored_path)

            # 分块写入，避免把大视频一次性读入内存。
            size = 0
            async with aiofiles.open(stored_path, "wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_size:
                        raise HTTPException(
                            status_code=413,
                            detail=f"文件 {file.filename} 超过大小限制",
                        )
                    await output.write(chunk)

            image_created_at = None
            width = None
            height = None
            if file_type == "image":
                try:
                    image_created_at, width, height = inspect_image(stored_path)
                except (UnidentifiedImageError, OSError) as exc:
                    raise HTTPException(
                        status_code=400,
                        detail=f"文件 {file.filename} 不是有效图片或图片已损坏",
                    ) from exc

            db.add(
                FileRecord(
                    id=file_id,
                    filename=file.filename or stored_path.name,
                    stored_path=str(stored_path),
                    file_type=file_type,
                    mime_type=content_type,
                    size=size,
                    width=width,
                    height=height,
                    session_id=session_id,
                    image_created_at=image_created_at,
                )
            )
            previews.append(
                {
                    "file_id": file_id,
                    "url": f"/files/uploads/{stored_path.name}",
                    "type": file_type,
                    "image_created_at": (
                        image_created_at.isoformat() if image_created_at else None
                    ),
                }
            )

        db.commit()
    except Exception:
        db.rollback()
        for path in saved_paths:
            path.unlink(missing_ok=True)
        raise
    finally:
        for file in files:
            await file.close()

    return {
        "code": 200,
        "message": "上传成功",
        "data": {
            "file_ids": [item["file_id"] for item in previews],
            "previews": previews,
            "session_id": session_id,
        },
    }
