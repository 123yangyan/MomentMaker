from typing import Any, Literal

from pydantic import BaseModel, Field

TemplateType = Literal["heat", "paint", "festival"]
StyleType = Literal["anime", "cyber", "realistic"]
MaterialType = Literal["sticker", "receipt", "postcard", "comicbook"]


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Any = None


class TaskStartRequest(BaseModel):
    # 上传 1～20 张；GLM 全量评分后自动选择最高 1～4 张用于生图。
    file_ids: list[str] = Field(min_length=1, max_length=20)
    template: TemplateType
    # 当前前端没有单独的风格控件，默认使用二次元；保留字段方便后续扩展。
    style: StyleType = "anime"
    # 前端物料卡片是单选：sticker / receipt / postcard / comicbook。
    material: MaterialType
    story_text: str | None = Field(default=None, max_length=500)
    work_title: str = Field(default="未命名作品", min_length=1, max_length=30)


class ComposeRequest(BaseModel):
    selected_elements: list[str] = Field(min_length=1)
    element_order: list[str] = Field(min_length=1)
    work_title: str = Field(min_length=1, max_length=30)


class ReplaceElementRequest(BaseModel):
    file_id: str = Field(min_length=1)


class PublishWorkRequest(BaseModel):
    task_id: str
    nickname: str = Field(default="匿名用户", min_length=1, max_length=20)
    material: list[MaterialType] = Field(min_length=1)
