import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from config import MOCK_DIR
from database import get_db
from models import Task, Work
from schemas import PublishWorkRequest

router = APIRouter(tags=["广场作品"])


@router.get("/works")
def get_works(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    demo: bool = False,
    db: Session = Depends(get_db),
):
    """按发布时间倒序获取广场作品。"""
    if demo:
        with (MOCK_DIR / "works.json").open("r", encoding="utf-8") as file:
            return {"code": 200, "message": "success", "data": json.load(file)}

    total = db.query(Work).count()
    works = (
        db.query(Work)
        .order_by(Work.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "code": 200,
        "message": "success",
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "work_id": work.id,
                    "title": work.title,
                    "cover_url": work.cover_url,
                    "template": work.template,
                    "style": work.style,
                    "material": json.loads(work.material),
                    "nickname": work.nickname,
                    "likes": work.likes,
                    "created_at": work.created_at.isoformat(),
                }
                for work in works
            ],
        },
    }


@router.post("/works")
def publish_work(
    body: PublishWorkRequest,
    demo: bool = False,
    db: Session = Depends(get_db),
):
    """把已经完成的任务发布为广场作品。"""
    if demo:
        return {
            "code": 200,
            "message": "发布成功（演示模式）",
            "data": {
                "work_id": "demo-work-001",
                "share_url": "/?work=demo-work-001",
                "cover_url": "/files/mock/result.svg",
            },
        }

    task = db.get(Task, body.task_id)
    if task is None or task.status != "succeeded" or not task.result_url:
        raise HTTPException(status_code=400, detail="任务不存在或尚未完成")

    work = Work(
        title=task.work_title or "未命名作品",
        cover_url=task.result_url,
        result_urls=json.dumps([task.result_url]),
        template=task.template,
        style=task.style,
        material=json.dumps(body.material),
        nickname=body.nickname,
    )
    db.add(work)
    db.commit()
    db.refresh(work)
    return {
        "code": 200,
        "message": "发布成功",
        "data": {
            "work_id": work.id,
            # 返回相对路径，前端可自动拼接当前域名。
            "share_url": f"/?work={work.id}",
            "cover_url": work.cover_url,
        },
    }


@router.post("/works/{work_id}/like")
def like_work(work_id: str, db: Session = Depends(get_db)):
    """MVP 简化版点赞：每次请求增加一次。"""
    work = db.get(Work, work_id)
    if work is None:
        raise HTTPException(status_code=404, detail="作品不存在")

    work.likes += 1
    db.commit()
    return {"code": 200, "message": "点赞成功", "data": {"likes": work.likes}}


def _serialize_work_detail(work: Work) -> dict:
    return {
        "work_id": work.id,
        "title": work.title,
        "cover_url": work.cover_url,
        "result_urls": json.loads(work.result_urls or "[]"),
        "template": work.template,
        "style": work.style,
        "material": json.loads(work.material),
        "nickname": work.nickname,
        "likes": work.likes,
        "created_at": work.created_at.isoformat(),
    }


@router.get("/works/{work_id}")
def get_work_detail(
    work_id: str,
    demo: bool = False,
    db: Session = Depends(get_db),
):
    """获取单个作品详情，供分享链接和 Lightbox 使用。"""
    if demo or work_id == "demo-work-001":
        with (MOCK_DIR / "work_detail.json").open("r", encoding="utf-8") as file:
            return {"code": 200, "message": "success", "data": json.load(file)}

    work = db.get(Work, work_id)
    if work is None:
        raise HTTPException(status_code=404, detail="作品不存在")

    return {
        "code": 200,
        "message": "success",
        "data": _serialize_work_detail(work),
    }
