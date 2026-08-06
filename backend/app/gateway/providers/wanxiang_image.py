"""通义万相 2.7 图像厂商（真实接入，同步 multimodal-generation 接口）。

套餐内可用模型：wan2.7-image / wan2.7-image-pro
- 接口：POST /api/v1/services/aigc/multimodal-generation/generation（同步）
- 请求体采用 messages 风格（与 wanx2.1-t2i-turbo 不同），单轮对话返回图片 URL
- wan2.7-image-pro 文生图支持 4K，质量更好；wan2.7-image 速度更快

对外接口与 mock_image 同名同签名：generate_character_ref /
generate_expression / generate_keyframe，均返回相对 URL 字符串。

调用方注意：本模块为同步实现（httpx.Client），
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
    if not settings.image_api_key:
        raise ProviderError(
            "未配置 DASHSCOPE_API_KEY：请在 backend/.env 填写阿里云百炼 API Key "
            "（或保持 MOCK_MODE=true 使用模拟模式）")
    return {"Authorization": f"Bearer {settings.image_api_key}",
            "Content-Type": "application/json"}


def _extract_image_url(resp_json: dict) -> str:
    """从万相 2.7 同步响应中稳健提取图片 URL。

    响应结构（实际可能因版本略有差异）：
      {"output": {"choices": [{"message": {"content": [{"image": "https://..."}]}}]}}
    或：
      {"output": {"results": [{"url": "https://..."}]}}
    """
    out = resp_json.get("output") or {}

    # 路径1：choices[].message.content[].image
    for choice in (out.get("choices") or []):
        msg = choice.get("message") or {}
        for item in (msg.get("content") or []):
            if isinstance(item, dict) and item.get("image"):
                return item["image"]
            if isinstance(item, str) and item.startswith("http"):
                return item

    # 路径2：results[].url（兼容旧格式）
    for r in (out.get("results") or []):
        if isinstance(r, dict) and r.get("url"):
            return r["url"]

    # 路径3：直接 url 字段
    if out.get("url"):
        return out["url"]

    # 路径4：顶层 choices（部分版本无 output 包裹）
    for choice in (resp_json.get("choices") or []):
        msg = choice.get("message") or {}
        for item in (msg.get("content") or []):
            if isinstance(item, dict) and item.get("image"):
                return item["image"]

    raise ProviderError(f"万相 2.7 响应未包含图片 URL：{str(resp_json)[:300]}")


def _gen_image(prompt: str, size: str = "2K", max_retries: int = 5,
               model: str | None = None) -> tuple[str, str]:
    """调用万相 2.7 同步文生图，下载结果图到本地 storage。

    返回 (本地相对URL, 万相原始公网URL)。公网URL供图生视频直接使用，绕过公网穿透依赖。
    size: "1K" / "2K" / "4K"（wan2.7-image-pro 文生图支持 4K）
    model: None 时用 .env 默认模型；可传 wan2.7-image / wan2.7-image-pro
    429 限流时指数退避重试。
    """
    url = f"{settings.image_base_url.rstrip('/')}/api/v1/services/aigc/multimodal-generation/generation"
    body = {
        "model": model or settings.DASHSCOPE_IMAGE_MODEL,
        "input": {
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ]
        },
        "parameters": {"size": size, "n": 1, "watermark": False},
    }
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            time.sleep(1.0)  # 提交间隔，降低 429 风险
            resp = _get_client().post(url, headers=_headers(), json=body)
            if resp.status_code == 429:
                wait = 15 * (attempt + 1)
                logger.warning("万相 2.7 限流（429），%ds 后重试（第 %d/%d 次）",
                               wait, attempt + 1, max_retries)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            img_url = _extract_image_url(resp.json())
            return _download(img_url), img_url   # (本地相对URL, 万相原始公网URL)
        except httpx.HTTPStatusError as exc:
            last_err = exc
            if resp.status_code == 429:
                continue
            raise ProviderError(
                f"万相 2.7 调用失败 HTTP {exc.response.status_code}: "
                f"{exc.response.text[:300]}") from exc
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            last_err = exc
            logger.warning("万相 2.7 调用异常（第 %d/%d 次）：%s",
                           attempt + 1, max_retries, exc)
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            raise ProviderError(f"万相 2.7 调用失败: {exc}") from exc
    raise ProviderError(f"万相 2.7 限流，已重试 {max_retries} 次仍失败（{last_err}）")


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


# ---------- 对外 API（与 mock_image 同名同签名） ----------
def generate_character_ref(character_name: str, appearance: str, seed: int,
                           model: str | None = None) -> str:
    """生成单张角色三视图候选图（正面/侧面/背面）。用于候选抽卡，不同 seed 产出不同变体。"""
    prompt = prompt_builder.character_threeview(character_name, appearance)
    local, _src = _gen_image(prompt, size="2K", model=model)
    return local


def generate_expression(character_name: str, appearance: str, emotion: str, seed: int,
                        model: str | None = None) -> str:
    """生成角色表情候选图。使用与选中三视图相同的 seed + 详细外貌描述，增强角色一致性。"""
    prompt = prompt_builder.character_expression(character_name, appearance, emotion)
    local, _src = _gen_image(prompt, size="2K", model=model)
    return local


def generate_keyframe(shot_no: int, scene_desc: str, prompt_zh: str, char_names: list[str],
                      seed: int, round_no: int, model: str | None = None) -> tuple[str, str]:
    """生成关键帧，返回 (本地相对URL, 万相原始公网URL)。

    公网URL供图生视频(i2v)直接使用，使本地开发环境无需配置 STORAGE_PUBLIC_BASE 公网穿透。
    """
    chars = "、".join(char_names[:3]) or "主角"
    prompt = (f"{prompt_zh}。角色：{chars}。竖屏 9:16 漫画关键帧构图，"
              f"远景环境交代+主体动作清晰，漫画分镜风格，电影级光影，"
              f"高清细节，构图考究，色彩明快，符合国漫审美，无文字水印")
    local, source = _gen_image(prompt, size="2K", model=model)
    return local, source
