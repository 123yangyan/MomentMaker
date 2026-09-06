"""调用硅基流动 GLM-4.5V，对单张图片进行结构化评分。"""

from __future__ import annotations

import base64
import io
import json
import re
import time
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from config import (
    AI_MAX_RETRIES,
    AI_REQUEST_TIMEOUT_SECONDS,
    SILICONFLOW_API_KEY,
    VL_MODEL,
)

API_URL = "https://api.siliconflow.cn/v1/chat/completions"

PROMPT = """你是图像生成参考图筛选专家。当前任务：把真实人物融合成漫画风格黑客松纪念海报，需要「人物身份清晰、五官可见、姿态可用」的参考照片。

请只评估这张图作为「人物参考图」是否合适。按下面维度各打 1-10 分（10 最好），并给出总分 1-10：
- face_clarity: 人脸是否清晰、五官能看清
- identity: 发型/服装/体型是否足够保留身份
- pose: 姿态是否自然、适合作为生成参考
- occlusion: 遮挡越少分越高
- sharpness: 对焦、模糊、过曝欠曝
- clutter: 背景杂乱/多人抢镜越少分越高
- overall: 综合是否推荐用于生成图

同时给出 recommend、80字内中文 reason 和 people_count。
严格只输出一个 JSON 对象，所有分数字段必须是 1 到 10 的整数，禁止写 0：
{"face_clarity":8,"identity":7,"pose":7,"occlusion":8,"sharpness":8,"clutter":7,"overall":8,"recommend":true,"reason":"人物清晰可用","people_count":1}
"""


class ProviderError(RuntimeError):
    """携带可记录元数据的第三方服务错误。"""

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        http_status: int | None = None,
        elapsed_ms: int | None = None,
        retry_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.elapsed_ms = elapsed_ms
        self.retry_count = retry_count


def _to_data_url(path: Path, max_side: int = 1280) -> str:
    """缩小图片后转成 data URL，降低请求体积和接口耗时。"""
    with Image.open(path) as image:
        image = image.convert("RGB")
        width, height = image.size
        if max(width, height) > max_side:
            scale = max_side / max(width, height)
            image = image.resize(
                (round(width * scale), round(height * scale)),
                Image.Resampling.LANCZOS,
            )
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _parse_score(content: str) -> dict[str, Any]:
    """兼容模型偶尔附加代码块或特殊标记，但严格校验评分字段。"""
    match = re.search(r"\{[\s\S]*\}", (content or "").strip())
    if not match:
        raise ValueError("模型响应中没有 JSON 对象")
    result = json.loads(match.group(0))

    score_fields = (
        "face_clarity",
        "identity",
        "pose",
        "occlusion",
        "sharpness",
        "clutter",
        "overall",
    )
    for field in score_fields:
        value = result.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"评分字段 {field} 不是数字")
        # 模型偶尔照抄示例里的 0；夹到 1-10，避免整单任务因此失败。
        value = max(1, min(10, int(value)))
        result[field] = value

    result["recommend"] = bool(result.get("recommend", False))
    result["reason"] = str(result.get("reason", ""))[:500]
    result["people_count"] = max(0, int(result.get("people_count", 0)))
    return result


def score_image(
    image_path: str | Path,
    *,
    api_key: str = SILICONFLOW_API_KEY,
    model: str = VL_MODEL,
) -> dict[str, Any]:
    """同步评分一张图片；应从 FastAPI 后台线程中调用。"""
    if not api_key:
        raise ProviderError("服务端缺少 SILICONFLOW_API_KEY", code="missing_api_key")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": _to_data_url(Path(image_path))},
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
        "temperature": 0.2,
        "max_tokens": 500,
        "enable_thinking": False,
    }
    started = time.perf_counter()
    last_error: Exception | None = None
    last_status: int | None = None

    for attempt in range(AI_MAX_RETRIES + 1):
        try:
            response = httpx.post(
                API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=AI_REQUEST_TIMEOUT_SECONDS,
            )
            last_status = response.status_code
            # 只有限流或服务端故障适合自动重试，4xx 参数错误不应重复消费。
            if response.status_code == 429 or response.status_code >= 500:
                response.raise_for_status()
            if response.is_error:
                detail = response.text[:300]
                raise ProviderError(
                    f"GLM 请求失败：HTTP {response.status_code} {detail}",
                    code="http_error",
                    http_status=response.status_code,
                    retry_count=attempt,
                )

            body = response.json()
            choices = body.get("choices") or []
            content = ((choices[0].get("message") or {}).get("content") if choices else "")
            score = _parse_score(content)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            return {
                "score": score,
                "usage": body.get("usage") or {},
                "request_id": response.headers.get("x-request-id")
                or body.get("request_id"),
                "http_status": response.status_code,
                "elapsed_ms": elapsed_ms,
                "retry_count": attempt,
                "model": body.get("model") or model,
            }
        except ProviderError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if attempt < AI_MAX_RETRIES:
                time.sleep(2**attempt)
                continue
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < AI_MAX_RETRIES:
                time.sleep(2**attempt)
                continue
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            raise ProviderError(
                f"GLM 响应格式错误：{exc}",
                code="invalid_response",
                http_status=last_status,
                elapsed_ms=elapsed_ms,
                retry_count=attempt,
            ) from exc

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    raise ProviderError(
        f"GLM 请求在重试后仍失败：{last_error}",
        code="request_failed",
        http_status=last_status,
        elapsed_ms=elapsed_ms,
        retry_count=AI_MAX_RETRIES,
    )
