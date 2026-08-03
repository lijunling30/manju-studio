"""通义万相（DashScope）视频厂商（真实接入：图生视频，异步任务式）。

流程：提交图生视频任务（X-DashScope-Async: enable）→ 轮询任务状态 →
下载成片 mp4 到本地 storage/videos/，返回 {video_url, preview_url, frames, duration, mock}。

注意：图生视频要求关键帧为「公网可访问」URL，部署后需配置
STORAGE_PUBLIC_BASE（config.py）；未配置时抛出清晰错误提示。

调用方注意：本模块为同步实现（httpx.Client + time.sleep 轮询），
请在异步任务层用 asyncio.to_thread 包装，避免阻塞事件循环。
"""
import logging
import time

import httpx

from ...config import settings
from ...storage import save_bytes
from ..base import ProviderError

logger = logging.getLogger("manju.gateway.wanxiang_video")

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=settings.AI_HTTP_TIMEOUT)
    return _client


def _headers() -> dict:
    if not settings.DASHSCOPE_API_KEY:
        raise ProviderError(
            "未配置 DASHSCOPE_API_KEY：请在 backend/.env 填写阿里云百炼 API Key "
            "（或保持 MOCK_MODE=true 使用模拟模式）")
    return {"Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}"}


def _public_url(keyframe_rel: str) -> str:
    """将 /storage/... 相对路径转为公网 URL（图生视频必需）。"""
    if not settings.STORAGE_PUBLIC_BASE:
        raise ProviderError(
            "图生视频需要关键帧公网可访问：请在 backend/.env 配置 "
            "STORAGE_PUBLIC_BASE（例：https://api.example.com 或 OSS 域名）")
    return f"{settings.STORAGE_PUBLIC_BASE.rstrip('/')}{keyframe_rel}"


def _submit_video(img_url: str, prompt: str, duration: int) -> str:
    """提交图生视频异步任务，返回 task_id。"""
    url = f"{settings.DASHSCOPE_BASE_URL.rstrip('/')}/api/v1/services/aigc/video-generation/video-synthesis"
    body = {
        "model": settings.DASHSCOPE_VIDEO_MODEL,
        "input": {"img_url": img_url, "prompt": prompt},
        "parameters": {"duration": duration, "resolution": "720*1280"},
    }
    try:
        resp = _get_client().post(url, headers={**_headers(), "Content-Type": "application/json",
                                                "X-DashScope-Async": "enable"}, json=body)
        resp.raise_for_status()
        return resp.json()["output"]["task_id"]
    except httpx.HTTPStatusError as exc:
        raise ProviderError(
            f"通义万相视频提交失败 HTTP {exc.response.status_code}: {exc.response.text[:300]}") from exc
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise ProviderError(f"通义万相视频提交失败: {exc}") from exc


def _wait_task(task_id: str, timeout: float, interval: float) -> str:
    """轮询直至成功，返回成片 URL；失败抛 ProviderError。"""
    url = f"{settings.DASHSCOPE_BASE_URL.rstrip('/')}/api/v1/tasks/{task_id}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(interval)
        try:
            resp = _get_client().get(url, headers=_headers())
            resp.raise_for_status()
            out = resp.json().get("output") or {}
            status = out.get("task_status", "PENDING")
        except httpx.HTTPError as exc:
            raise ProviderError(f"通义万相视频查询任务失败: {exc}") from exc

        if status == "SUCCEEDED":
            url = (out.get("video_url")
                   or ((out.get("results") or [{}])[0].get("url"))
                   or (out.get("output") or {}).get("video_url")
                   or "")
            if not url:
                raise ProviderError("通义万相视频任务成功但无成片 URL")
            return url
        if status in ("FAILED", "CANCELED"):
            code = out.get("code", "")
            msg = out.get("message", "")
            raise ProviderError(f"通义万相视频任务{status}（{code} {msg}）")
        logger.info("通义万相视频任务 %s 状态 %s，继续等待", task_id, status)
    raise ProviderError(f"通义万相视频任务超时（>{int(timeout)}s）")


def generate_video(keyframe_rel: str, duration: float, vendor: str, seed: int,
                   fail_times: int = 0, attempt: int = 1) -> dict:
    """图生视频完整流程，返回 {video_url, preview_url, frames, duration, mock}。

    duration 超出厂商支持范围（4-8s）时按边界截断。
    """
    if fail_times >= attempt:
        raise ProviderError(f"{vendor} 任务失败（第 {attempt} 次尝试，用于重试/降级验证）")

    clip = max(4, min(8, int(round(duration))))
    img_url = _public_url(keyframe_rel)
    task_id = _submit_video(img_url, "镜头运动自然，主体连贯，电影感运镜", clip)
    video_url = _wait_task(task_id, settings.AI_VIDEO_TASK_TIMEOUT,
                           settings.AI_TASK_POLL_INTERVAL)

    # 下载成片到本地 storage
    try:
        resp = _get_client().get(video_url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ProviderError(f"下载成片失败: {exc}") from exc
    local = save_bytes(resp.content, "videos", ".mp4")

    return {"video_url": local, "preview_url": keyframe_rel, "frames": [],
            "duration": clip, "mock": False}
