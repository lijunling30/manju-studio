"""通义万相（DashScope）图像厂商（真实接入，异步任务式）。

流程：提交文生图任务（X-DashScope-Async: enable）→ 轮询任务状态 →
下载结果图到本地 storage/，返回 /storage/images/xxx.png（与 mock 同格式）。

对外接口与 mock_image 同名同签名：generate_character_ref /
generate_expression / generate_keyframe，均返回相对 URL 字符串。

调用方注意：本模块为同步实现（httpx.Client + time.sleep 轮询），
请在异步任务层用 asyncio.to_thread 包装，避免阻塞事件循环。
"""
import logging
import time

import httpx

from ...config import settings
from ...storage import save_bytes
from ..base import ProviderError
from .. import prompt_builder

logger = logging.getLogger("manju.gateway.wanxiang")

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


def _submit_text2image(prompt: str, size: str, n: int = 1, max_retries: int = 5) -> str:
    """提交文生图异步任务，返回 task_id。429 限流时自动等待重试。"""
    url = f"{settings.DASHSCOPE_BASE_URL.rstrip('/')}/api/v1/services/aigc/text2image/image-synthesis"
    body = {
        "model": settings.DASHSCOPE_IMAGE_MODEL,
        "input": {"prompt": prompt},
        "parameters": {"size": size, "n": n},
    }
    headers = {**_headers(), "Content-Type": "application/json",
               "X-DashScope-Async": "enable"}
    for attempt in range(max_retries):
        try:
            resp = _get_client().post(url, headers=headers, json=body)
            if resp.status_code == 429:
                wait = 15 * (attempt + 1)  # 15, 30, 45, 60, 75 秒递增退避
                logger.warning("通义万相限流（429），%ds 后重试（第 %d/%d 次）",
                               wait, attempt + 1, max_retries)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()["output"]["task_id"]
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"通义万相提交失败 HTTP {exc.response.status_code}: {exc.response.text[:300]}") from exc
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ProviderError(f"通义万相提交失败: {exc}") from exc
    raise ProviderError(f"通义万相限流，已重试 {max_retries} 次仍失败（请稍后再试）")


def _wait_task(task_id: str, timeout: float, interval: float) -> list[str]:
    """轮询异步任务直至成功，返回结果 URL 列表；失败抛 ProviderError。"""
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
            raise ProviderError(f"通义万相查询任务失败: {exc}") from exc

        if status == "SUCCEEDED":
            results = [r["url"] for r in (out.get("results") or [])]
            if not results:
                raise ProviderError("通义万相任务成功但无结果图")
            return results
        if status in ("FAILED", "CANCELED"):
            code = out.get("code", "")
            msg = out.get("message", "")
            raise ProviderError(f"通义万相任务{status}（{code} {msg}）")
        # PENDING / RUNNING → 继续轮询
        logger.info("通义万相任务 %s 状态 %s，继续等待", task_id, status)
    raise ProviderError(f"通义万相任务超时（>{int(timeout)}s）")


def _download(url: str) -> str:
    """下载结果图到本地 storage，返回相对 URL。"""
    try:
        resp = _get_client().get(url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ProviderError(f"下载结果图失败: {exc}") from exc
    ext = ".png"
    low = (url.split("?")[0] or "").lower()
    for e in (".jpg", ".jpeg", ".webp", ".png"):
        if low.endswith(e):
            ext = e
            break
    return save_bytes(resp.content, "images", ext)


def _gen_image(prompt: str, size: str = "720*1280") -> str:
    """一次文生图完整流程（提交 → 轮询 → 下载第一张）。"""
    time.sleep(1.5)  # 提交间隔，降低请求频率避免厂商 API 限流（429）
    task_id = _submit_text2image(prompt, size)
    urls = _wait_task(task_id, settings.AI_IMAGE_TASK_TIMEOUT, settings.AI_TASK_POLL_INTERVAL)
    return _download(urls[0])


def _style_hint() -> str:
    return ("漫画分镜风格，电影级光影，高清细节，构图考究，"
            "色彩明快，符合国漫审美，无文字水印")


# ---------- 对外 API（与 mock_image 同名同签名） ----------
def generate_character_ref(character_name: str, appearance: str, seed: int) -> str:
    """生成单张角色三视图候选图（正面/侧面/背面）。用于候选抽卡，不同 seed 产出不同变体。"""
    prompt = prompt_builder.character_threeview(character_name, appearance)
    return _gen_image(prompt, size="1024*1024")


def generate_expression(character_name: str, appearance: str, emotion: str, seed: int) -> str:
    """生成角色表情候选图。使用与选中三视图相同的 seed + 详细外貌描述，增强角色一致性。"""
    prompt = prompt_builder.character_expression(character_name, appearance, emotion)
    return _gen_image(prompt, size="1024*1024")


def generate_keyframe(shot_no: int, scene_desc: str, prompt_zh: str, char_names: list[str],
                      seed: int, round_no: int) -> str:
    chars = "、".join(char_names[:3]) or "主角"
    prompt = (f"{prompt_zh}。角色：{chars}。竖屏 9:16 漫画关键帧构图，"
              f"远景环境交代+主体动作清晰，{_style_hint()}")
    return _gen_image(prompt, size="720*1280")
