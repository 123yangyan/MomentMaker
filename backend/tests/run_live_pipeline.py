"""手动真实联调脚本：会调用两个收费 API，并保留任务和生成结果。"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from main import app  # noqa: E402
from models import ApiCallLog, ImageScore, Task, TaskEvent  # noqa: E402


def main() -> int:
    source_dir = PROJECT_DIR / "图片"
    source_paths = [
        source_dir / "06705b1c6d0382f487df3680245c8dd9.jpg",
        source_dir / "b2d10511b0d15134fe56f634604f68ff.jpg",
        source_dir / "bc4af07fcbbb9214682957e91340bd1c.png",
        source_dir / "d6d961f97205a5035f18ec50180de5ce.jpg",
    ]
    missing = [str(path) for path in source_paths if not path.exists()]
    if missing:
        print(json.dumps({"error": "测试图片不存在", "missing": missing}, ensure_ascii=False))
        return 2

    # 当前素材目录有 4 张图片；重复前两张作为独立上传项，组成 6 张测试输入。
    six_inputs = source_paths + source_paths[:2]
    session_id = str(uuid.uuid4())
    opened_files = []
    try:
        multipart = []
        for index, path in enumerate(six_inputs, start=1):
            handle = path.open("rb")
            opened_files.append(handle)
            mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            multipart.append(("files", (f"live_{index}{path.suffix}", handle, mime)))

        with TestClient(app) as client:
            upload = client.post(
                "/api/upload",
                files=multipart,
                headers={"X-Session-Id": session_id},
            )
            upload.raise_for_status()
            file_ids = upload.json()["data"]["file_ids"]
            print(json.dumps({"stage": "uploaded", "count": len(file_ids)}, ensure_ascii=False))

            # TestClient 会等待 FastAPI BackgroundTasks 完成，因此本请求可能持续数分钟。
            start = client.post(
                "/api/task/start",
                headers={"X-Session-Id": session_id},
                json={
                    "file_ids": file_ids,
                    "template": "heat",
                    "style": "anime",
                    "material": "postcard",
                    "work_title": "真实 API 第一阶段测试",
                },
            )
            start.raise_for_status()
            task_id = start.json()["data"]["task_id"]

            status = client.get(
                f"/api/task/{task_id}/status",
                headers={"X-Session-Id": session_id},
            )
            status.raise_for_status()
            task_data = status.json()["data"]

        db = SessionLocal()
        try:
            task = db.get(Task, task_id)
            scores = (
                db.query(ImageScore)
                .filter(ImageScore.task_id == task_id)
                .order_by(ImageScore.upload_order)
                .all()
            )
            calls = db.query(ApiCallLog).filter(ApiCallLog.task_id == task_id).all()
            events = db.query(TaskEvent).filter(TaskEvent.task_id == task_id).count()
            summary = {
                "task_id": task_id,
                "status": task.status,
                "progress": task.progress,
                "scores": [
                    {
                        "file_id": row.file_id,
                        "overall": row.overall,
                        "status": row.status,
                        "elapsed_ms": row.elapsed_ms,
                    }
                    for row in scores
                ],
                "selected_file_ids": json.loads(task.selected_file_ids or "[]"),
                "api_calls": [
                    {
                        "provider": row.provider,
                        "status": row.status,
                        "model": row.model,
                        "elapsed_ms": row.elapsed_ms,
                        "retry_count": row.retry_count,
                    }
                    for row in calls
                ],
                "event_count": events,
                "result_url": task.result_url,
                "error_code": task.error_code,
                "error_message": task.error_message,
                "status_api_matches_db": task_data["status"] == task.status,
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0 if task.status == "succeeded" else 1
        finally:
            db.close()
    finally:
        for handle in opened_files:
            handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
