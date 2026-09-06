"""后端端到端测试：上传、评分、自动选 1～4 张、生图与发布。"""

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

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal, recover_stuck_tasks  # noqa: E402
from main import app  # noqa: E402
from models import ApiCallLog, FileRecord, ImageScore, Task, TaskEvent, Work  # noqa: E402


def _jpeg_bytes(index: int) -> bytes:
    image = Image.new("RGB", (320, 240), (30 * index, 20 * index, 10 * index))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


class PipelineIntegrationTest(unittest.TestCase):
    def _fake_score_factory(self, score_values: list[int | None]):
        score_index = 0

        def fake_score_image(_path: str, **_kwargs) -> dict:
            nonlocal score_index
            if score_index >= len(score_values) or score_values[score_index] is None:
                from ai.vl_scoring import ProviderError

                score_index += 1
                raise ProviderError("模拟评分失败", code="provider_error")

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

        return fake_score_image

    def _fake_generate_poster(self, expected_count: int | None = None):
        generated: list[Path] = []

        def fake_generate_poster(paths, output_path, **kwargs) -> dict:
            if expected_count is not None:
                self.assertEqual(len(paths), expected_count)
            result_path = Path(output_path)
            Image.new("RGB", (900, 1600), "pink").save(result_path, "JPEG")
            generated.append(result_path)
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

        fake_generate_poster.generated = generated
        return fake_generate_poster

    def _cleanup_task(self, task_id: str | None, uploaded_ids: list[str]) -> None:
        db = SessionLocal()
        try:
            if task_id:
                db.query(Work).filter(Work.task_id == task_id).delete()
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

    def test_single_image_pipeline_selects_one(self) -> None:
        session_id = str(uuid.uuid4())
        uploaded_ids: list[str] = []
        task_id: str | None = None
        fake_generate = self._fake_generate_poster(expected_count=1)

        try:
            with (
                patch(
                    "routers.task.score_image",
                    side_effect=self._fake_score_factory([8]),
                ),
                patch("routers.task.generate_poster", side_effect=fake_generate),
                TestClient(app) as client,
            ):
                upload = client.post(
                    "/api/upload",
                    files=[("files", ("one.jpg", _jpeg_bytes(1), "image/jpeg"))],
                    headers={"X-Session-Id": session_id},
                )
                uploaded_ids = upload.json()["data"]["file_ids"]
                start = client.post(
                    "/api/task/start",
                    headers={"X-Session-Id": session_id},
                    json={
                        "file_ids": uploaded_ids,
                        "template": "heat",
                        "material": "postcard",
                        "work_title": "单图测试",
                    },
                )
                task_id = start.json()["data"]["task_id"]
                status = client.get(
                    f"/api/task/{task_id}/status",
                    headers={"X-Session-Id": session_id},
                ).json()["data"]
                self.assertEqual(status["status"], "succeeded")
                self.assertEqual(status["selected_count"], 1)
                self.assertEqual(status["selected_file_ids"], uploaded_ids)
                square = client.get("/api/works").json()["data"]["items"]
                self.assertTrue(any(item["title"] == "单图测试" for item in square))
        finally:
            for path in fake_generate.generated:
                path.unlink(missing_ok=True)
            self._cleanup_task(task_id, uploaded_ids)

    def test_upload_score_select_generate_and_persist(self) -> None:
        session_id = str(uuid.uuid4())
        uploaded_ids: list[str] = []
        task_id: str | None = None
        fake_generate = self._fake_generate_poster(expected_count=4)

        try:
            with (
                patch(
                    "routers.task.score_image",
                    side_effect=self._fake_score_factory([6, 10, 8, 7, 9, 5]),
                ),
                patch("routers.task.generate_poster", side_effect=fake_generate),
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
                uploaded_ids = upload.json()["data"]["file_ids"]
                start = client.post(
                    "/api/task/start",
                    headers={"X-Session-Id": session_id},
                    json={
                        "file_ids": uploaded_ids,
                        "template": "heat",
                        "material": "postcard",
                        "story_text": "突出团队协作",
                        "work_title": "六图离线测试",
                    },
                )
                task_id = start.json()["data"]["task_id"]
                status = client.get(
                    f"/api/task/{task_id}/status",
                    headers={"X-Session-Id": session_id},
                ).json()["data"]
                self.assertEqual(status["status"], "succeeded")
                self.assertEqual(status["selected_count"], 4)

            db = SessionLocal()
            try:
                task = db.get(Task, task_id)
                self.assertEqual(
                    json.loads(task.selected_file_ids),
                    [uploaded_ids[1], uploaded_ids[4], uploaded_ids[2], uploaded_ids[3]],
                )
            finally:
                db.close()
        finally:
            for path in fake_generate.generated:
                path.unlink(missing_ok=True)
            self._cleanup_task(task_id, uploaded_ids)

    def test_partial_score_failure_still_generates(self) -> None:
        session_id = str(uuid.uuid4())
        uploaded_ids: list[str] = []
        task_id: str | None = None
        fake_generate = self._fake_generate_poster(expected_count=2)

        try:
            with (
                patch(
                    "routers.task.score_image",
                    side_effect=self._fake_score_factory([9, None, 7]),
                ),
                patch("routers.task.generate_poster", side_effect=fake_generate),
                TestClient(app) as client,
            ):
                upload = client.post(
                    "/api/upload",
                    files=[
                        ("files", (f"t{i}.jpg", _jpeg_bytes(i), "image/jpeg"))
                        for i in range(1, 4)
                    ],
                    headers={"X-Session-Id": session_id},
                )
                uploaded_ids = upload.json()["data"]["file_ids"]
                start = client.post(
                    "/api/task/start",
                    headers={"X-Session-Id": session_id},
                    json={
                        "file_ids": uploaded_ids,
                        "template": "paint",
                        "material": "receipt",
                        "work_title": "部分失败测试",
                    },
                )
                task_id = start.json()["data"]["task_id"]
                status = client.get(
                    f"/api/task/{task_id}/status",
                    headers={"X-Session-Id": session_id},
                ).json()["data"]
                self.assertEqual(status["status"], "succeeded")
                self.assertEqual(status["failed_images"], 1)
                self.assertEqual(status["selected_count"], 2)
        finally:
            for path in fake_generate.generated:
                path.unlink(missing_ok=True)
            self._cleanup_task(task_id, uploaded_ids)

    def test_publish_requires_session_and_blocks_duplicate(self) -> None:
        session_id = str(uuid.uuid4())
        other_session = str(uuid.uuid4())
        uploaded_ids: list[str] = []
        task_id: str | None = None
        fake_generate = self._fake_generate_poster(expected_count=1)

        try:
            with (
                patch(
                    "routers.task.score_image",
                    side_effect=self._fake_score_factory([8]),
                ),
                patch("routers.task.generate_poster", side_effect=fake_generate),
                TestClient(app) as client,
            ):
                upload = client.post(
                    "/api/upload",
                    files=[("files", ("one.jpg", _jpeg_bytes(1), "image/jpeg"))],
                    headers={"X-Session-Id": session_id},
                )
                uploaded_ids = upload.json()["data"]["file_ids"]
                start = client.post(
                    "/api/task/start",
                    headers={"X-Session-Id": session_id},
                    json={
                        "file_ids": uploaded_ids,
                        "template": "festival",
                        "material": "sticker",
                        "work_title": "发布测试",
                    },
                )
                task_id = start.json()["data"]["task_id"]

                forbidden = client.post(
                    "/api/works",
                    headers={"X-Session-Id": other_session},
                    json={
                        "task_id": task_id,
                        "material": ["sticker"],
                        "nickname": "他人",
                    },
                )
                self.assertEqual(forbidden.status_code, 403)

                published = client.post(
                    "/api/works",
                    headers={"X-Session-Id": session_id},
                    json={
                        "task_id": task_id,
                        "material": ["sticker"],
                        "nickname": "本人",
                    },
                )
                # 生成成功时已自动上广场，再次发布应被拒绝。
                self.assertEqual(published.status_code, 400)

                mine = client.get(
                    "/api/works/mine",
                    headers={"X-Session-Id": session_id},
                ).json()["data"]["items"]
                self.assertEqual(len(mine), 1)
                self.assertEqual(mine[0]["title"], "发布测试")
        finally:
            for path in fake_generate.generated:
                path.unlink(missing_ok=True)
            self._cleanup_task(task_id, uploaded_ids)

    def test_recover_stuck_tasks_marks_failed(self) -> None:
        session_id = str(uuid.uuid4())
        db = SessionLocal()
        task_id = str(uuid.uuid4())
        try:
            db.add(
                Task(
                    id=task_id,
                    status="scoring",
                    progress=20,
                    file_ids='["fake"]',
                    session_id=session_id,
                    template="heat",
                    style="anime",
                    material='["postcard"]',
                )
            )
            db.commit()
            recovered = recover_stuck_tasks()
            self.assertGreaterEqual(recovered, 1)
            task = db.get(Task, task_id)
            self.assertEqual(task.status, "failed")
            self.assertEqual(task.error_code, "server_restarted")
        finally:
            db.query(TaskEvent).filter(TaskEvent.task_id == task_id).delete()
            db.query(Task).filter(Task.id == task_id).delete()
            db.commit()
            db.close()


if __name__ == "__main__":
    unittest.main()
