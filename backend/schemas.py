from typing import Any, Literal

from pydantic import BaseModel, Field

TemplateType = Literal["comic", "map", "album"]
StyleType = Literal["anime", "cyber", "realistic"]
MaterialType = Literal["keychain", "badge", "postcard"]


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Any = None


class TaskStartRequest(BaseModel):
    # Seedream 最终需要 4 张参考图，因此任务至少上传 4 张图片。
    file_ids: list[str] = Field(min_length=4, max_length=20)
    template: TemplateType
    # 当前前端没有单独的风格控件，默认使用二次元；保留字段方便后续扩展。
    style: StyleType = "anime"
    # 前端物料卡片是单选，因此任务接口只接收一个物料类型。
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
