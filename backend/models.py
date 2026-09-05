import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class FileRecord(Base):
    """用户上传的原始文件。"""

    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(20))
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[int] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # 图片自身 EXIF 中的拍摄时间；视频或无 EXIF 信息的图片为空。
    image_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Task(Base):
    """素材处理及成品合成任务。"""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    file_ids: Mapped[str] = mapped_column(Text)
    selected_file_ids: Mapped[str] = mapped_column(Text, default="[]")
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    template: Mapped[str] = mapped_column(String(50))
    style: Mapped[str] = mapped_column(String(50))
    material: Mapped[str] = mapped_column(Text)
    story_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    work_title: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # elements 字段为兼容旧数据库保留，新流水线不再执行抠图。
    elements: Mapped[str] = mapped_column(Text, default="[]")
    vl_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image_model_requested: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image_model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    result_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    internal_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ImageScore(Base):
    """GLM-4.5V 对任务中一张图片给出的结构化评分。"""

    __tablename__ = "image_scores"
    __table_args__ = (UniqueConstraint("task_id", "file_id", name="uq_task_file_score"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id"), index=True
    )
    file_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("files.id"), index=True
    )
    upload_order: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    face_clarity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    identity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pose: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occlusion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sharpness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clutter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommend: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    people_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ApiCallLog(Base):
    """第三方 API 调用的脱敏日志，不保存密钥和图片 Base64。"""

    __tablename__ = "api_call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id"), index=True
    )
    provider: Mapped[str] = mapped_column(String(30))
    stage: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    usage_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TaskEvent(Base):
    """任务状态变化事件，用于排查任务卡在哪个阶段。"""

    __tablename__ = "task_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    progress: Mapped[int] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Work(Base):
    """发布到广场的作品。"""

    __tablename__ = "works"
    __table_args__ = (UniqueConstraint("task_id", name="uq_work_task_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(30), default="未命名作品")
    cover_url: Mapped[str] = mapped_column(String(500))
    result_urls: Mapped[str] = mapped_column(Text)
    template: Mapped[str] = mapped_column(String(50))
    style: Mapped[str] = mapped_column(String(50))
    material: Mapped[str] = mapped_column(Text)
    nickname: Mapped[str] = mapped_column(String(100), default="匿名用户")
    likes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
