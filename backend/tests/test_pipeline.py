"""后端第一阶段端到端测试：上传 6 张图并跑完整任务流水线。"""

from __future__ import annotations

import io
import json
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

# 测试从 backend 目录或项目根目录运行时，都能导入后端模块。
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from main import app  # noqa: E402
from models import ApiCallLog, FileRecord, ImageScore, Task, TaskEvent  # noqa: E402


def _jpeg_bytes(index: int) -> bytes:
    """生成颜色不同的有效测试图片，不依赖仓库外部素材。"""
    image = Image.new("RGB", (320, 240), (30 * index, 20 * index, 10 * index))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


class PipelineIntegrationTest(unittest.TestCase):
    def test_upload_score_select_generate_and_persist(self) -> None:
        session_id = str(uuid.uuid4())
        uploaded_ids: list[str] = []
        task_id: str | None = None
        generated_result: Path | None = None
        score_values = [6, 10, 8, 7, 9, 5]
        score_index = 0

        def fake_score_image(_path: str, **_kwargs) -> dict:
            nonlocal score_index
            overall = score_values[score_index]
            score_index += 1
            return {
                "score": {
                    "face_clarity": overall,
                    "identity": overall,
                    "pose": overall,
                    "occlusion": overall,
                    "sharpness": overall,
                    "clutter": overall,
                    "overall": overall,
                    "recommend": overall >= 7,
                    "reason": f"离线测试分数 {overall}",
                    "people_count": 1,
                },
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                "request_id": f"glm-test-{score_index}",
                "http_status": 200,
                "elapsed_ms": 10,
                "retry_count": 0,
                "model": "zai-org/GLM-4.5V",
            }

        def fake_generate_poster(paths, output_path, **kwargs) -> dict:
            nonlocal generated_result
            self.assertEqual(len(paths), 4)
            # 验证前端结构化选项已经由后端转换为受控提示词。
            prompt = kwargs["prompt"]
            self.assertIn("日系少年漫画连环画模板", prompt)
            self.assertIn("成品用于明信片", prompt)
            self.assertIn("<user_story>突出团队协作</user_story>", prompt)
            generated_result = Path(output_path)
            Image.new("RGB", (900, 1600), "pink").save(generated_result, "JPEG")
            return {
                "usage": {"generated_images": 1, "total_tokens": 123},
                "request_id": "seedream-test-1",
                "http_status": 200,
                "elapsed_ms": 20,
                "retry_count": 0,
                "model_requested": "test-seedream",
                "model_used": "test-seedream",
                "size": "900x1600",
            }

        try:
            with (
                patch("routers.task.score_image", side_effect=fake_score_image),
                patch("routers.task.generate_poster", side_effect=fake_generate_poster),
                TestClient(app) as client,
            ):
                files = [
                    ("files", (f"test_{index}.jpg", _jpeg_bytes(index), "image/jpeg"))
                    for index in range(1, 7)
                ]
                upload = client.post(
                    "/api/upload",
                    files=files,
                    headers={"X-Session-Id": session_id},
                )
                self.assertEqual(upload.status_code, 200, upload.text)
                upload_data = upload.json()["data"]
                uploaded_ids = upload_data["file_ids"]
                self.assertEqual(len(uploaded_ids), 6)
                self.assertEqual(upload_data["session_id"], session_id)

                start = client.post(
                    "/api/task/start",
                    headers={"X-Session-Id": session_id},
                    json={
                        "file_ids": uploaded_ids,
                        "template": "comic",
                        # style 可不传，后端默认使用 anime。
                        "material": "postcard",
                        "story_text": "突出团队协作",
                        "work_title": "第一阶段离线测试",
                    },
                )
                self.assertEqual(start.status_code, 200, start.text)
                task_id = start.json()["data"]["task_id"]

                status = client.get(
                    f"/api/task/{task_id}/status",
                    headers={"X-Session-Id": session_id},
                )
                self.assertEqual(status.status_code, 200, status.text)
                data = status.json()["data"]
                self.assertEqual(data["status"], "succeeded")
                self.assertEqual(data["progress"], 100)
                self.assertTrue(data["result_url"].endswith(f"{task_id}.jpg"))

            db = SessionLocal()
            try:
                task = db.get(Task, task_id)
                self.assertIsNotNone(task)
                self.assertEqual(json.loads(task.selected_file_ids), [
                    uploaded_ids[1],
                    uploaded_ids[4],
                    uploaded_ids[2],
                    uploaded_ids[3],
                ])
                self.assertEqual(
                    db.query(ImageScore).filter(ImageScore.task_id == task_id).count(),
                    6,
                )
                self.assertEqual(
                    db.query(ApiCallLog).filter(ApiCallLog.task_id == task_id).count(),
                    7,
                )
                event_statuses = [
                    row.status
                    for row in db.query(TaskEvent)
                    .filter(TaskEvent.task_id == task_id)
                    .all()
                ]
                self.assertIn("scoring", event_statuses)
                self.assertIn("generating", event_statuses)
                self.assertIn("succeeded", event_statuses)
            finally:
                db.close()
        finally:
            # 测试结束后清理数据库和上传/生成文件，避免污染真实演示数据。
            db = SessionLocal()
            try:
                if task_id:
                    db.query(ApiCallLog).filter(ApiCallLog.task_id == task_id).delete()
                    db.query(ImageScore).filter(ImageScore.task_id == task_id).delete()
                    db.query(TaskEvent).filter(TaskEvent.task_id == task_id).delete()
                    db.query(Task).filter(Task.id == task_id).delete()
                records = (
                    db.query(FileRecord).filter(FileRecord.id.in_(uploaded_ids)).all()
                    if uploaded_ids
                    else []
                )
                for record in records:
                    Path(record.stored_path).unlink(missing_ok=True)
                    db.delete(record)
                db.commit()
            finally:
                db.close()
            if generated_result:
                generated_result.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
