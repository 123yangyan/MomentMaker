"""图片评分、选四张和 Seedream 生图任务接口。"""

from __future__ import annotations

import json
import traceback
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ai.poster_generation import generate_poster
from ai.prompt_builder import PROMPT_VERSION, build_poster_prompt
from ai.vl_scoring import ProviderError, score_image
from config import ARK_IMAGE_MODEL, RESULTS_DIR, VL_MODEL
from database import SessionLocal, get_db
from models import ApiCallLog, FileRecord, ImageScore, Task, TaskEvent
from schemas import TaskStartRequest

router = APIRouter(tags=["生成任务"])


class WorkflowError(RuntimeError):
    """可安全展示给用户的业务流程错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _set_state(
    db: Session,
    task: Task,
    status: str,
    progress: int,
    message: str | None = None,
) -> None:
    """同步更新任务快照和事件表，方便前端轮询及后台排错。"""
    task.status = status
    task.progress = progress
    db.add(
        TaskEvent(
            task_id=task.id,
            status=status,
            progress=progress,
            message=message,
        )
    )
    db.commit()


def _save_api_log(
    db: Session,
    task_id: str,
    *,
    provider: str,
    stage: str,
    model: str,
    status: str,
    result: dict | None = None,
    error: ProviderError | None = None,
) -> None:
    """只保存调用元数据，不保存密钥、请求头和图片 Base64。"""
    result = result or {}
    db.add(
        ApiCallLog(
            task_id=task_id,
            provider=provider,
            stage=stage,
            model=str(result.get("model") or result.get("model_used") or model),
            status=status,
            http_status=result.get("http_status")
            if error is None
            else error.http_status,
            request_id=result.get("request_id"),
            elapsed_ms=result.get("elapsed_ms")
            if error is None
            else error.elapsed_ms,
            retry_count=result.get("retry_count", 0)
            if error is None
            else error.retry_count,
            usage_json=json.dumps(result.get("usage") or {}, ensure_ascii=False),
            error_message=str(error)[:500] if error else None,
        )
    )


def _save_successful_score(
    db: Session,
    task: Task,
    record: FileRecord,
    upload_order: int,
    result: dict,
) -> ImageScore:
    score = result["score"]
    usage = result.get("usage") or {}
    row = ImageScore(
        task_id=task.id,
        file_id=record.id,
        upload_order=upload_order,
        model=str(result.get("model") or task.vl_model),
        status="succeeded",
        face_clarity=score["face_clarity"],
        identity_score=score["identity"],
        pose=score["pose"],
        occlusion=score["occlusion"],
        sharpness=score["sharpness"],
        clutter=score["clutter"],
        overall=score["overall"],
        recommend=score["recommend"],
        reason=score["reason"],
        people_count=score["people_count"],
        elapsed_ms=result.get("elapsed_ms"),
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        retry_count=result.get("retry_count", 0),
    )
    db.add(row)
    return row


def run_ai_task(task_id: str, file_ids: list[str]) -> None:
    """后台执行完整流水线，并在每张图片完成后持久化进度。"""
    db = SessionLocal()
    task = db.get(Task, task_id)
    if task is None:
        db.close()
        return

    try:
        task.started_at = datetime.now(UTC)
        _set_state(db, task, "scoring", 5, "开始使用 GLM-4.5V 对图片评分")

        rows = db.query(FileRecord).filter(FileRecord.id.in_(file_ids)).all()
        records_by_id = {row.id: row for row in rows}
        records = [records_by_id[file_id] for file_id in file_ids]
        successful: list[ImageScore] = []
        failure_codes: list[str] = []

        for index, record in enumerate(records):
            try:
                result = score_image(record.stored_path, model=task.vl_model or VL_MODEL)
                score_row = _save_successful_score(db, task, record, index, result)
                successful.append(score_row)
                _save_api_log(
                    db,
                    task.id,
                    provider="siliconflow",
                    stage="score_image",
                    model=task.vl_model or VL_MODEL,
                    status="succeeded",
                    result=result,
                )
            except ProviderError as exc:
                failure_codes.append(exc.code)
                db.add(
                    ImageScore(
                        task_id=task.id,
                        file_id=record.id,
                        upload_order=index,
                        model=task.vl_model or VL_MODEL,
                        status="failed",
                        elapsed_ms=exc.elapsed_ms,
                        retry_count=exc.retry_count,
                        error_code=exc.code,
                        error_message=str(exc)[:500],
                    )
                )
                _save_api_log(
                    db,
                    task.id,
                    provider="siliconflow",
                    stage="score_image",
                    model=task.vl_model or VL_MODEL,
                    status="failed",
                    error=exc,
                )

            # 评分阶段占总进度的 50%，逐张提交后刷新页面也不会丢失记录。
            progress = 5 + round(50 * (index + 1) / len(records))
            _set_state(
                db,
                task,
                "scoring",
                progress,
                f"已完成 {index + 1}/{len(records)} 张图片评分",
            )

        if len(successful) < 4:
            code = (
                "missing_api_key"
                if failure_codes and set(failure_codes) == {"missing_api_key"}
                else "insufficient_scores"
            )
            raise WorkflowError(code, "成功评分的图片少于 4 张，无法生成海报")

        _set_state(db, task, "selecting", 60, "正在选择评分最高的 4 张图片")
        # 分数相同时依次看人脸、身份、清晰度，最后保持较早上传的图片优先。
        selected = sorted(
            successful,
            key=lambda row: (
                row.overall or 0,
                row.face_clarity or 0,
                row.identity_score or 0,
                row.sharpness or 0,
                -row.upload_order,
            ),
            reverse=True,
        )[:4]
        selected_ids = [row.file_id for row in selected]
        task.selected_file_ids = json.dumps(selected_ids)
        db.commit()

        _set_state(db, task, "generating", 65, "正在调用 Seedream 融合生图")
        result_path = RESULTS_DIR / f"{task.id}.jpg"
        selected_paths = [records_by_id[file_id].stored_path for file_id in selected_ids]
        try:
            # 前端只传结构化选项，最终提示词由服务端统一构建和版本管理。
            selected_materials = json.loads(task.material or "[]")
            if len(selected_materials) != 1:
                raise WorkflowError("invalid_material", "生成任务必须且只能选择一种物料")
            prompt = build_poster_prompt(
                task.template,
                selected_materials[0],
                style=task.style,
                story_text=task.story_text,
            )
            poster_result = generate_poster(
                selected_paths,
                result_path,
                prompt=prompt,
                model=task.image_model_requested or ARK_IMAGE_MODEL,
            )
            _save_api_log(
                db,
                task.id,
                provider="volcengine_ark",
                stage="generate_poster",
                model=task.image_model_requested or ARK_IMAGE_MODEL,
                status="succeeded",
                result=poster_result,
            )
            db.commit()
        except ProviderError as exc:
            _save_api_log(
                db,
                task.id,
                provider="volcengine_ark",
                stage="generate_poster",
                model=task.image_model_requested or ARK_IMAGE_MODEL,
                status="failed",
                error=exc,
            )
            db.commit()
            raise WorkflowError(exc.code, str(exc)) from exc

        _set_state(db, task, "downloading", 95, "生成图已转存到本地")
        task.result_url = f"/files/results/{result_path.name}"
        task.image_model_used = poster_result["model_used"]
        task.status = "succeeded"
        task.progress = 100
        task.error_code = None
        task.error_message = None
        task.internal_error = None
        task.completed_at = datetime.now(UTC)
        db.add(
            TaskEvent(
                task_id=task.id,
                status="succeeded",
                progress=100,
                message="海报生成完成",
            )
        )
        db.commit()
    except WorkflowError as exc:
        db.rollback()
        task = db.get(Task, task_id)
        if task is not None:
            task.status = "failed"
            task.error_code = exc.code
            task.error_message = str(exc)[:500]
            task.internal_error = traceback.format_exc()[:4000]
            task.completed_at = datetime.now(UTC)
            db.add(
                TaskEvent(
                    task_id=task.id,
                    status="failed",
                    progress=task.progress,
                    message=task.error_message,
                )
            )
            db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        task = db.get(Task, task_id)
        if task is not None:
            task.status = "failed"
            task.error_code = "internal_error"
            task.error_message = "任务处理失败，请稍后重试"
            task.internal_error = traceback.format_exc()[:4000]
            task.completed_at = datetime.now(UTC)
            db.add(
                TaskEvent(
                    task_id=task.id,
                    status="failed",
                    progress=task.progress,
                    message=f"内部错误：{type(exc).__name__}",
                )
            )
            db.commit()
    finally:
        db.close()


def _parse_session_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="X-Session-Id 必须是有效 UUID") from exc


@router.post("/task/start")
def start_task(
    body: TaskStartRequest,
    background_tasks: BackgroundTasks,
    x_session_id: str = Header(...),
    db: Session = Depends(get_db),
):
    """创建任务后立即返回 task_id，耗时模型调用在后台线程完成。"""
    session_id = _parse_session_id(x_session_id)
    unique_file_ids = list(dict.fromkeys(body.file_ids))
    if len(unique_file_ids) < 4:
        raise HTTPException(status_code=400, detail="至少需要 4 张不同的图片")

    records = db.query(FileRecord).filter(FileRecord.id.in_(unique_file_ids)).all()
    records_by_id = {record.id: record for record in records}
    missing_ids = [file_id for file_id in unique_file_ids if file_id not in records_by_id]
    if missing_ids:
        raise HTTPException(status_code=400, detail=f"文件不存在：{missing_ids}")
    if any(record.session_id != session_id for record in records):
        raise HTTPException(status_code=403, detail="不能使用其他匿名会话上传的文件")
    if any(record.file_type != "image" for record in records):
        raise HTTPException(status_code=400, detail="第一阶段只支持图片，不支持视频")

    task = Task(
        file_ids=json.dumps(unique_file_ids),
        selected_file_ids="[]",
        session_id=session_id,
        template=body.template,
        style=body.style,
        # 数据库沿用 JSON 数组格式，兼容作品发布和既有查询逻辑。
        material=json.dumps([body.material]),
        story_text=body.story_text,
        work_title=body.work_title,
        vl_model=VL_MODEL,
        image_model_requested=ARK_IMAGE_MODEL,
        prompt_version=PROMPT_VERSION,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    db.add(
        TaskEvent(
            task_id=task.id,
            status="pending",
            progress=0,
            message="任务已创建，等待后台处理",
        )
    )
    db.commit()

    background_tasks.add_task(run_ai_task, task.id, unique_file_ids)
    return {
        "code": 200,
        "message": "任务创建成功",
        "data": {"task_id": task.id, "status": task.status, "progress": 0},
    }


@router.get("/task/{task_id}/status")
def get_task_status(
    task_id: str,
    x_session_id: str = Header(...),
    db: Session = Depends(get_db),
):
    """返回任务快照和已成功产生的评分，供前端每两秒轮询。"""
    session_id = _parse_session_id(x_session_id)
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.session_id != session_id:
        raise HTTPException(status_code=403, detail="不能查看其他匿名会话的任务")

    scores = (
        db.query(ImageScore)
        .filter(ImageScore.task_id == task.id, ImageScore.status == "succeeded")
        .order_by(ImageScore.upload_order)
        .all()
    )
    selected_file_ids = json.loads(task.selected_file_ids or "[]")
    selected_ids = set(selected_file_ids)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "task_id": task.id,
            "status": task.status,
            "progress": task.progress,
            "completed_images": len(scores),
            "total_images": len(json.loads(task.file_ids)),
            "selected_file_ids": selected_file_ids,
            "scores": [
                {
                    "file_id": row.file_id,
                    "overall": row.overall,
                    "face_clarity": row.face_clarity,
                    "identity": row.identity_score,
                    "sharpness": row.sharpness,
                    "recommend": row.recommend,
                    "reason": row.reason,
                    "selected": row.file_id in selected_ids,
                }
                for row in scores
            ],
            "result_url": task.result_url,
            "error_code": task.error_code,
            "error_message": task.error_message,
        },
    }
