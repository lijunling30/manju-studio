"""Qwen-Audio-TTS 语音合成厂商（真实接入，同步 HTTP 接口）。

套餐内可用模型：qwen-audio-3.0-tts-plus（实时语音合成）
- 接口：POST /api/v1/services/audio/tts/SpeechSynthesizer
- Token Plan (sk-sp-) 必须使用 token-plan.cn-beijing.maas.aliyuncs.com 域名
- 请求体：input 里直接含 text/voice/format/sample_rate（无 parameters 字段）
- 响应：JSON，音频 URL 在 output.audio.url（需下载到本地 storage）

注意：qwen-audio-3.0-tts-plus 底层为 cosyvoice 引擎，不支持 [happy] 等富语言标签
（插入会导致 Engine error 411）。情绪表现通过音色选择 + 文本语调自然传达。

对外接口与 mock_audio.generate_voice 同名同签名，返回相对 URL 字符串。

调用方注意：本模块为同步实现（httpx.Client），
请在异步任务层用 asyncio.to_thread 包装，避免阻塞事件循环。
"""
import logging
import time

import httpx

from ...config import settings
from ...storage import save_bytes
from ..base import ProviderError

logger = logging.getLogger("manju.gateway.qwen_tts")

_client: httpx.Client | None = None

# 平台 voice_id 到 Qwen-Audio-TTS 真实音色的映射
# 注意：当前 Token Plan 套餐内 qwen-audio-3.0-tts-plus 仅支持 longanhuan_v3.6 一个音色
# （其他音色如 longxiaochun_v3.6 会返回 Engine error 411）。
# 套餐升级后可在此扩展更多音色，或改为按角色性别动态选择。
_VOICE_MAP = {
    "doubao_voice_1": "longanhuan_v3.6",   # 套餐限制：仅此音色可用
    "doubao_voice_2": "longanhuan_v3.6",
    "doubao_voice_3": "longanhuan_v3.6",
    "female": "longanhuan_v3.6",
    "male": "longanhuan_v3.6",
    "default": "longanhuan_v3.6",
}


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
    return {"Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
            "Content-Type": "application/json"}


def _resolve_voice(voice_id: str) -> str:
    """把平台 voice_id 映射为 Qwen-Audio 真实音色 ID。"""
    if not voice_id:
        return settings.DASHSCOPE_TTS_VOICE
    # 若 voice_id 已是真实音色名（long 前缀，或含 _v3. 这类版本后缀），直接透传
    # 注意：不能用 "_v" in voice_id，会误匹配 doubao_voice_1 里的 "_v"
    if voice_id.startswith("long") or "_v3." in voice_id or "_v2." in voice_id:
        return voice_id
    return _VOICE_MAP.get(voice_id) or settings.DASHSCOPE_TTS_VOICE


def _extract_audio_url(resp_json: dict) -> str:
    """从 TTS JSON 响应中提取音频 URL。

    响应结构：
      {"output": {"audio": {"url": "http://...", "data": "", ...}, "finish_reason": "stop"},
       "usage": {"characters": 18}, "request_id": "..."}
    """
    out = resp_json.get("output") or {}
    audio = out.get("audio") or {}
    if isinstance(audio, dict):
        if audio.get("url"):
            return audio["url"]
        if audio.get("data"):
            # base64 数据兜底
            import base64
            try:
                raw = base64.b64decode(audio["data"])
                ext = ".mp3" if settings.DASHSCOPE_TTS_FORMAT == "mp3" else ".wav"
                return save_bytes(raw, "audio", ext)
            except Exception as exc:
                raise ProviderError(f"解析 TTS base64 音频失败: {exc}") from exc
    # 兼容其他可能字段
    if out.get("url"):
        return out["url"]
    raise ProviderError(f"Qwen-Audio-TTS 响应未包含音频 URL：{str(resp_json)[:300]}")


def generate_voice(text: str, voice_id: str, emotion: str,
                   duration: float, seed: int,
                   model: str | None = None, voice_override: str | None = None) -> str:
    """调用 Qwen-Audio-TTS 同步合成，下载音频到本地 storage，返回相对 URL。

    与 mock_audio.generate_voice 同签名（增加可选 model/voice_override），无缝替换。
    model: None 时用 .env 默认 TTS 模型
    voice_override: None 时用 voice_id 经 _resolve_voice 映射后的音色
    响应为 JSON，音频 URL 在 output.audio.url。
    注意：emotion 参数当前不转换为富语言标签（cosyvoice 引擎不支持），
    情绪表现通过音色选择 + 文本语调自然传达。
    """
    if not text or not text.strip():
        raise ProviderError("TTS 待合成文本为空")

    url = f"{settings.DASHSCOPE_BASE_URL.rstrip('/')}/api/v1/services/audio/tts/SpeechSynthesizer"
    # voice_override 优先（用户设置中指定的音色），否则用 voice_id 映射
    resolved_voice = voice_override or _resolve_voice(voice_id)
    # Token Plan 请求体：input 内直接含 format/sample_rate（无 parameters 字段）
    body = {
        "model": model or settings.DASHSCOPE_TTS_MODEL,
        "input": {
            "text": text,   # 纯文本，不加富语言标签（cosyvoice 引擎不支持）
            "voice": resolved_voice,
            "format": settings.DASHSCOPE_TTS_FORMAT,
            "sample_rate": 24000,
        },
    }

    max_retries = 3
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            time.sleep(0.5)  # 提交间隔，降低 429 风险
            resp = _get_client().post(url, headers=_headers(), json=body)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                logger.warning("Qwen-Audio-TTS 限流（429），%ds 后重试（第 %d/%d 次）",
                               wait, attempt + 1, max_retries)
                time.sleep(wait)
                continue
            resp.raise_for_status()

            # 响应为 JSON，包含音频 URL
            audio_url = _extract_audio_url(resp.json())
            return _download(audio_url)
        except httpx.HTTPStatusError as exc:
            last_err = exc
            if resp.status_code == 429:
                continue
            raise ProviderError(
                f"Qwen-Audio-TTS 调用失败 HTTP {exc.response.status_code}: "
                f"{exc.response.text[:300]}") from exc
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            last_err = exc
            logger.warning("Qwen-Audio-TTS 调用异常（第 %d/%d 次）：%s",
                           attempt + 1, max_retries, exc)
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            raise ProviderError(f"Qwen-Audio-TTS 调用失败: {exc}") from exc
    raise ProviderError(f"Qwen-Audio-TTS 限流，已重试 {max_retries} 次仍失败（{last_err}）")


def _download(url: str) -> str:
    """下载音频到本地 storage，返回相对 URL。"""
    try:
        resp = _get_client().get(url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ProviderError(f"下载 TTS 音频失败: {exc}") from exc
    ext = f".{settings.DASHSCOPE_TTS_FORMAT}" if settings.DASHSCOPE_TTS_FORMAT in (
        "mp3", "wav", "pcm", "opus") else ".mp3"
    return save_bytes(resp.content, "audio", ext)

