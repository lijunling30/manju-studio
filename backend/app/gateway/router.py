"""AI 模型网关（L4）★自建核心★。

统一封装所有厂商调用：一种请求格式适配所有厂商；支持厂商路由/降级/重试/成本记账；
确认闸口支撑（估计成本 + 复述需求）；中文提示词后台静默翻译（M4，mock 下原文直用）。
业务层禁止直连厂商——一律经本模块。
"""
from ..config import settings
from ..core import costs as cost_model
from .base import ProviderError
from .providers import (deepseek_llm, mock_audio, mock_image, mock_llm,
                        mock_moderation, mock_video, wanxiang_image,
                        wanxiang_video)


class Gateway:
    """模型网关单例。MOCK_MODE=true 走模拟厂商；false 走真实厂商。

    真实厂商：
      - 文本：DeepSeek（小说/剧本/分镜/复述，长内容生成）
      - 图像：通义万相（角色图/表情/关键帧，异步任务式）
      - 视频：通义万相（图生视频，异步任务式）
    音频 / 审核暂无真实 API，MOCK_MODE=false 时仍走模拟实现。
    """

    # ---------- 厂商路由 ----------
    def _vendor(self, module: str, hint: str | None = None) -> str:
        if hint:
            return hint
        table = {
            "novel": settings.text_vendors, "script": settings.text_vendors,
            "shot": settings.text_vendors, "restate": settings.text_vendors,
            "character": settings.image_vendors, "keyframe": settings.image_vendors,
            "video": settings.video_vendors, "audio_tts": ["doubao_tts", "cosyvoice"],
            "bgm": ["sky_music", "netease_tianyin"], "sfx": ["doubao_tts"],
            "render": ["ffmpeg"], "compliance": ["aliyun_sec"],
        }
        vendors = table.get(module, settings.text_vendors)
        return vendors[0]

    # ---------- 成本预估（确认卡必填项，5.0.1） ----------
    def estimate(self, module: str, params: dict) -> dict:
        vendor = self._vendor(module, params.get("vendor"))
        tokens = mock_llm.estimate_tokens(module, params)
        if module == "novel":
            return cost_model.estimate(module, vendor, tokens=tokens)
        if module == "script":
            return cost_model.estimate(module, vendor, tokens=tokens)
        if module == "shot":
            return cost_model.estimate(module, vendor, tokens=tokens,
                                       count=params.get("batch_count", 10))
        if module == "character":
            return cost_model.estimate(module, vendor, count=params.get("count", 3))
        if module == "keyframe":
            return cost_model.estimate(module, vendor, count=params.get("count", 2))
        if module == "video":
            return cost_model.estimate(module, vendor, duration=params.get("duration", 5.0))
        if module in ("audio_tts",):
            return cost_model.estimate(module, vendor, chars=len(params.get("text", "")))
        if module == "bgm":
            return cost_model.estimate(module, vendor, count=1)
        if module == "sfx":
            return cost_model.estimate(module, vendor, chars=max(1, len(params.get("text", ""))))
        if module == "render":
            # 按成片总时长计（各镜头视频时长之和）
            return cost_model.estimate(module, vendor, duration=params.get("total_duration", 60.0))
        if module == "compliance":
            return cost_model.estimate(module, vendor, count=params.get("count", 1))
        return cost_model.estimate(module, vendor)

    # ---------- 需求复述（确认卡：意图 + 输出物描述） ----------
    def restate(self, module: str, params: dict, batch_count: int,
                correction: str | None = None) -> tuple[str, str]:
        if not settings.MOCK_MODE:
            return deepseek_llm.restate(module, params, batch_count, correction)
        return mock_llm.restate(module, params, batch_count, correction)

    # ---------- 文本生成（同步，M2/M3/M4 的文本部分） ----------
    def generate_novel(self, genre: str, setting: str, protagonist: str,
                       chapter_count: int, seed: int, vendor: str | None = None) -> dict:
        vendor = self._vendor("novel", vendor)
        if not settings.MOCK_MODE:
            data = deepseek_llm.generate_novel_full(genre, setting, protagonist,
                                                    chapter_count, seed)
            return {**data, "vendor": vendor,
                    "amount": data["tokens"] / 1000 * cost_model.unit_price("text", vendor)}
        outline = mock_llm.generate_novel_outline(genre, setting, protagonist, chapter_count, seed)
        chapters = [
            {"no": c["no"], "title": c["title"],
             "content": mock_llm.generate_chapter(c, genre, setting, protagonist, seed)}
            for c in outline
        ]
        characters = mock_llm.generate_characters(protagonist, genre, seed)
        tokens = sum(len(ch["content"]) * 2 for ch in chapters)
        return {"outline": outline, "chapters": chapters, "characters": characters,
                "tokens": tokens, "vendor": vendor,
                "amount": tokens / 1000 * cost_model.unit_price("text", vendor)}

    def generate_script(self, title: str, chapters: list[dict], seed: int,
                        vendor: str | None = None) -> dict:
        vendor = self._vendor("script", vendor)
        if not settings.MOCK_MODE:
            scenes, curve = deepseek_llm.generate_scenes(title, chapters, seed)
        else:
            scenes, curve = mock_llm.generate_scenes(title, chapters, seed)
        tokens = 8000
        return {"scenes": scenes, "emotion_curve": curve, "tokens": tokens, "vendor": vendor,
                "amount": tokens / 1000 * cost_model.unit_price("text", vendor)}

    def generate_shots(self, scenes: list[dict], target_count: int, style_id: str,
                       char_names: list[str], seed: int, vendor: str | None = None) -> dict:
        vendor = self._vendor("shot", vendor)
        if not settings.MOCK_MODE:
            shots = deepseek_llm.generate_shots(scenes, target_count, style_id,
                                                char_names, seed)
        else:
            shots = mock_llm.generate_shots(scenes, target_count, style_id, char_names, seed)
        tokens = max(1, len(shots)) * 600
        return {"shots": shots, "tokens": tokens, "vendor": vendor,
                "amount": tokens / 1000 * cost_model.unit_price("text", vendor)}

    # ---------- 图像 / 视频 / 音频 / 审核 ----------
    def character_ref(self, name: str, appearance: str, seed: int, vendor: str | None = None) -> str:
        if not settings.MOCK_MODE:
            return wanxiang_image.generate_character_ref(name, appearance, seed)
        return mock_image.generate_character_ref(name, appearance, seed)

    def expression(self, name: str, appearance: str, emotion: str, seed: int) -> str:
        if not settings.MOCK_MODE:
            return wanxiang_image.generate_expression(name, appearance, emotion, seed)
        return mock_image.generate_expression(name, emotion, seed)

    def keyframe(self, shot_no: int, scene_desc: str, prompt_zh: str, char_names: list[str],
                 seed: int, round_no: int) -> str:
        if not settings.MOCK_MODE:
            return wanxiang_image.generate_keyframe(shot_no, scene_desc, prompt_zh,
                                                    char_names, seed, round_no)
        return mock_image.generate_keyframe(shot_no, scene_desc, prompt_zh, char_names, seed, round_no)

    def video(self, keyframe_rel: str, duration: float, vendor: str, seed: int,
              fail_times: int = 0, attempt: int = 1) -> dict:
        if not settings.MOCK_MODE:
            return wanxiang_video.generate_video(keyframe_rel, duration, vendor, seed,
                                                 fail_times, attempt)
        return mock_video.generate_video(keyframe_rel, duration, vendor, seed, fail_times, attempt)

    def voice(self, text: str, voice_id: str, emotion: str, duration: float, seed: int) -> str:
        return mock_audio.generate_voice(text, voice_id, emotion, duration, seed)

    def bgm(self, emotion: str, duration: float, seed: int) -> str:
        return mock_audio.generate_bgm(emotion, duration, seed)

    def sfx(self, kind: str, duration: float, seed: int) -> str:
        return mock_audio.generate_sfx(kind, duration, seed)

    def moderate(self, texts: list[str], vendor: str | None = None) -> dict:
        return mock_moderation.moderate_texts(texts, vendor=self._vendor("compliance", vendor))


gateway = Gateway()
