"""调用火山方舟 Seedream，把评分最高的 1～4 张图片融合为海报。"""

from __future__ import annotations

import base64
import io
import time
from pathlib import Path
from typing import Any, Sequence

import httpx
from PIL import Image

from ai.prompt_builder import PROMPT_VERSION
from ai.vl_scoring import ProviderError
from config import (
    AI_MAX_RETRIES,
    AI_REQUEST_TIMEOUT_SECONDS,
    ARK_API_KEY,
    ARK_IMAGE_MODEL,
    MAX_REFERENCE_IMAGES,
    MIN_REFERENCE_IMAGES,
)

API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
# 保留通用兜底提示词，正常业务调用应由 prompt_builder 传入组合后的提示词。
DEFAULT_PROMPT = """把图1到图4中的真实人物融合成一张竖版9:16日本少年漫画风格黑客松纪念海报。使用柔粉和晴空蓝的高饱和甜酷撞色，加入复古旧漫画印刷网点颗粒、速度线和分镜格。人物大动态破框而出，人物外貌、发型、服装尽量保持与参考照片一致。加入“GO HACK!”爆炸对话气泡、代码括号、BUILD SUCCESS 徽章、像素咖啡杯、闪电和星星贴纸。整体明快、有满幅动态感和商业海报质感，高清细节。"""


def _to_data_url(path: Path, max_side: int = 2048) -> str:
    """统一压缩四张参考图，避免原图 Base64 让请求体过大。"""
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
        image.save(buffer, format="JPEG", quality=90)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def generate_poster(
    image_paths: Sequence[str | Path],
    output_path: str | Path,
    *,
    prompt: str | None = None,
    api_key: str = ARK_API_KEY,
    model: str = ARK_IMAGE_MODEL,
) -> dict[str, Any]:
    """同步生成并转存海报；成功时返回可落库的脱敏调用信息。"""
    if not api_key:
        raise ProviderError("服务端缺少 ARK_API_KEY", code="missing_api_key")
    if not MIN_REFERENCE_IMAGES <= len(image_paths) <= MAX_REFERENCE_IMAGES:
        raise ValueError(
            f"Seedream 必须接收 {MIN_REFERENCE_IMAGES}～{MAX_REFERENCE_IMAGES} 张参考图片"
        )

    payload = {
        "model": model,
        "prompt": prompt or DEFAULT_PROMPT,
        "image": [_to_data_url(Path(path)) for path in image_paths],
        "size": "1K",
        "response_format": "url",
        "watermark": False,
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
            if response.status_code == 429 or response.status_code >= 500:
                response.raise_for_status()
            if response.is_error:
                detail = response.text[:300]
                code = "http_error"
                if "SensitiveContent" in detail or "PolicyViolation" in detail:
                    code = "sensitive_content"
                raise ProviderError(
                    f"Seedream 请求失败：HTTP {response.status_code} {detail}",
                    code=code,
                    http_status=response.status_code,
                    retry_count=attempt,
                )

            body = response.json()
            items = body.get("data") or []
            source_url = items[0].get("url") if items else None
            if not source_url:
                raise ProviderError(
                    "Seedream 成功响应中没有图片 URL",
                    code="empty_result",
                    http_status=response.status_code,
                    retry_count=attempt,
                )

            # 供应商 URL 约 24 小时后过期，因此在任务完成前下载到自己的目录。
            download = httpx.get(source_url, timeout=AI_REQUEST_TIMEOUT_SECONDS)
            download.raise_for_status()
            destination = Path(output_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_bytes(download.content)
            temporary.replace(destination)

            elapsed_ms = round((time.perf_counter() - started) * 1000)
            return {
                "usage": body.get("usage") or {},
                "request_id": response.headers.get("x-request-id")
                or body.get("request_id"),
                "http_status": response.status_code,
                "elapsed_ms": elapsed_ms,
                "retry_count": attempt,
                "model_requested": model,
                "model_used": body.get("model") or model,
                "size": items[0].get("size"),
            }
        except ProviderError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if attempt < AI_MAX_RETRIES:
                time.sleep(2**attempt)
                continue
        except (ValueError, KeyError) as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            raise ProviderError(
                f"Seedream 响应格式错误：{exc}",
                code="invalid_response",
                http_status=last_status,
                elapsed_ms=elapsed_ms,
                retry_count=attempt,
            ) from exc

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    raise ProviderError(
        f"Seedream 请求或图片下载在重试后仍失败：{last_error}",
        code="request_failed",
        http_status=last_status,
        elapsed_ms=elapsed_ms,
        retry_count=AI_MAX_RETRIES,
    )
