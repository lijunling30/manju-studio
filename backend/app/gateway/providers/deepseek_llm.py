"""DeepSeek LLM 厂商（真实接入，OpenAI 兼容接口）。

MOCK_MODE=false 时启用：小说 / 剧本 / 分镜 / 需求复述全部由真实大模型生成。
小说每章正文 ~NOVEL_CHAPTER_WORDS 字（默认 2500，可配置），解决
mock 模板「每章仅 4 段话、内容非常少」的问题；各章正文并行生成，
避免串行调用导致的长时间等待。

调用方注意：本模块为同步实现（httpx.Client），请在异步任务层用
asyncio.to_thread 包装，避免阻塞事件循环。
"""
import json
import logging
import random
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx

from ...config import settings
from ..base import ProviderError

logger = logging.getLogger("manju.gateway.deepseek")

_client: httpx.Client | None = None
_client_lock = threading.Lock()

# 每章目标字数（真实模式下覆盖 mock 的 4 段话）
_CHAPTER_WORDS = settings.NOVEL_CHAPTER_WORDS
_CHAPTER_MIN_WORDS = int(_CHAPTER_WORDS * 0.6)


def _get_client() -> httpx.Client:
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(timeout=settings.AI_HTTP_TIMEOUT)
        return _client


def _chat(messages: list[dict], *, json_mode: bool = False,
          temperature: float = 0.8, max_tokens: int | None = None,
          seed: int | None = None) -> str:
    """调用 DeepSeek chat completions，返回文本内容。"""
    if not settings.DEEPSEEK_API_KEY:
        raise ProviderError(
            "未配置 DEEPSEEK_API_KEY：请在 backend/.env 填写 DeepSeek API Key "
            "（或保持 MOCK_MODE=true 使用模拟模式）")
    body: dict = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if max_tokens:
        body["max_tokens"] = max_tokens
    if seed is not None:
        body["seed"] = seed
    url = f"{settings.DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"
    try:
        resp = _get_client().post(
            url, headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
            json=body)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        raise ProviderError(
            f"DeepSeek 调用失败 HTTP {exc.response.status_code}: "
            f"{exc.response.text[:300]}") from exc
    except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
        raise ProviderError(f"DeepSeek 调用失败: {exc}") from exc


def _extract_json(text: str) -> dict:
    """从 LLM 输出中稳健提取 JSON 对象（容忍代码块围栏/前后缀/截断）。"""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            raw = m.group(0)
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                # 容错：LLM 输出被截断时尝试补全闭合（大纲/分场等数组场景）
                repaired = _repair_truncated(raw)
                if repaired is not None:
                    return repaired
                raise ProviderError(
                    f"LLM 返回非法 JSON: {exc}\n原文前 200 字: {text[:200]}") from exc
        raise ProviderError(f"LLM 返回无法解析的内容: {text[:200]}")


def _repair_truncated(raw: str) -> dict | None:
    """尝试修复被截断的 JSON：在末尾补齐数组/对象闭合括号。

    例如 `{"outline": [{...}, {...},` → 补 `]}` 后解析成功。
    仅用于兜底；优先依赖重试拿到完整输出。
    """
    stripped = raw.rstrip().rstrip(", ")
    if not stripped:
        return None
    # 依次尝试：数组内截断补 }]}、对象内截断补 }
    for cand in (stripped + "]}", stripped + "}"):
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    return None


def _json_call(messages: list[dict], *, seed: int | None, max_tokens: int | None = None,
               retries: int = 2) -> dict:
    """JSON 模式调用并解析；解析失败自动换 seed 重试。

    DeepSeek json_object 模式偶发输出截断/非 JSON 内容，换 seed 重试
    通常能拿到完整结果（任务级重试 seed 不变，必须在此变化）。
    """
    last: Exception | None = None
    for attempt in range(retries):
        try:
            text = _chat(messages, json_mode=True, seed=(seed or 0) + attempt * 1000,
                         max_tokens=max_tokens)
            return _extract_json(text)
        except ProviderError as exc:
            last = exc
            logger.warning("DeepSeek JSON 解析失败（第 %d/%d 次）：%s",
                           attempt + 1, retries, exc)
    raise ProviderError(str(last)) from last


def _sys(role: str) -> str:
    return {"novel": "你是资深网络小说作家",
            "script": "你是资深影视编剧",
            "shot": "你是专业动画分镜师",
            "restate": "你是智能助手"}[role]


# ==================== 小说生成（M2，真实模式） ====================
def generate_novel_full(genre: str, setting: str, protagonist: str,
                        chapter_count: int, seed: int) -> dict:
    """一次完成大纲 + 角色表 + 各章正文（正文并行生成）。

    返回 {outline, chapters, characters, tokens}，格式与 mock 版一致。
    """
    if chapter_count <= 0:
        chapter_count = 1
    outline = _gen_outline(genre, setting, protagonist, chapter_count, seed)
    characters = _gen_characters(genre, protagonist, seed)

    briefs = [{"no": o["no"], "title": o["title"], "summary": o["summary"]}
              for o in outline]
    # 上一章概要用于保持剧情连贯
    for i, b in enumerate(briefs):
        b["prev_summary"] = briefs[i - 1]["summary"] if i > 0 else ""

    with ThreadPoolExecutor(max_workers=min(4, chapter_count)) as pool:
        futures = [pool.submit(_gen_chapter, b, genre, setting, protagonist, seed)
                   for b in briefs]
        chapters = []
        for f in futures:
            try:
                chapters.append(f.result())
            except Exception:
                logger.exception("DeepSeek 生成章节失败")
                raise
    tokens = sum(len(ch["content"]) * 2 for ch in chapters)
    return {"outline": outline, "chapters": chapters,
            "characters": characters, "tokens": tokens}


def _gen_outline(genre: str, setting: str, protagonist: str,
                 chapter_count: int, seed: int) -> list[dict]:
    prompt = (
        f"请为一部「{genre}」题材的漫画剧本小说创作 {chapter_count} 章的故事大纲。\n"
        f"世界观设定：{setting or '由你构思'}。主角：{protagonist or '由你命名'}。\n"
        f"要求：主线清晰、每章都有悬念钩子、爽点密集；"
        f"第 1 章交代背景，最后一章制造大高潮。\n"
        f"严格输出 JSON，格式："
        f'{{"outline": [{{"no": 章节序号从1开始, "title": "第X章 四字标题", '
        f'"summary": "本章剧情概要，50字左右"}}]}}，共 {chapter_count} 条。')
    data = _json_call([{"role": "system", "content": _sys("novel")},
                       {"role": "user", "content": prompt}],
                      seed=seed, max_tokens=2000)
    outline = data.get("outline") or []
    if not outline:
        raise ProviderError("DeepSeek 未返回大纲")
    # 规范化字段
    for i, o in enumerate(outline):
        o["no"] = int(o.get("no", i + 1))
        title = o.get("title", f"第{i + 1}章")
        o["title"] = title if title.startswith("第") else f"第{i + 1}章 {title}"
        o["summary"] = str(o.get("summary", "")).strip()
    return outline[:chapter_count]


def _gen_characters(genre: str, protagonist: str, seed: int) -> list[dict]:
    prompt = (
        f"为一部「{genre}」题材的小说设计主要角色表（主角必须是「{protagonist or '待定'}」）。\n"
        f"要求：共 4-5 人，包含主角/对手/挚友/关键配角等，每人给出外貌与性格描述。\n"
        f'严格输出 JSON：{{"characters": [{{"name": "名字", "role": "主角/对手/挚友/关键配角/神秘人物", '
        f'"desc": "外貌+性格，50字左右"}}]}}')
    data = _json_call([{"role": "system", "content": _sys("novel")},
                       {"role": "user", "content": prompt}],
                      seed=seed, max_tokens=1000)
    chars = data.get("characters") or []
    if not chars:
        return [{"name": protagonist or "主角", "role": "主角",
                 "desc": f"《{genre}》故事核心人物"}]
    if protagonist and not any(c["name"] == protagonist for c in chars):
        chars.insert(0, {"name": protagonist, "role": "主角",
                         "desc": f"《{genre}》故事核心人物，性格坚韧"})
    return chars


def _gen_chapter(brief: dict, genre: str, setting: str, protagonist: str,
                 seed: int) -> dict:
    prompt = (
        f"题材：{genre}\n世界观：{setting or '由你延续前文'}\n主角：{protagonist or '沿用前文'}\n"
        f"本章：{brief['title']}（第 {brief['no']} 章）\n本章概要：{brief['summary']}\n"
        f"前情概要：{brief['prev_summary'] or '本章为故事开端'}\n\n"
        f"请创作本章正文：约 {_CHAPTER_WORDS} 字（不得少于 {_CHAPTER_MIN_WORDS} 字），"
        f"包含环境描写、人物动作与对白，节奏紧凑、爽点密集，结尾留悬念。"
        f"只输出正文，不要输出章节标题。")
    content = _chat([{"role": "system", "content": _sys("novel")},
                     {"role": "user", "content": prompt}],
                    temperature=0.9, max_tokens=8000,
                    seed=seed + brief["no"] * 17).strip()
    if len(content) < 200:
        raise ProviderError(f"DeepSeek 章节内容过短（{len(content)} 字）")
    return {"no": brief["no"], "title": brief["title"], "content": content}


# ==================== 剧本结构化（M3，真实模式） ====================
def _chapter_briefs(chapters: list[dict]) -> str:
    """将小说章节压缩为供剧本生成的摘要（控制输入 token）。"""
    parts = []
    for ch in (chapters or [])[:12]:
        content = ch.get("content") or ""
        head = content[:400] if content else ""
        parts.append(f"第{ch.get('no', '?')}章《{ch.get('title', '')}》：{head}")
    return "\n".join(parts)


def generate_scenes(novel_title: str, chapters: list[dict], seed: int
                    ) -> tuple[list[dict], list[dict]]:
    prompt = (
        f"请将小说《{novel_title}》改编为漫画/动画剧本（分场脚本）。\n"
        f"小说内容（每章摘录）：\n{_chapter_briefs(chapters)}\n\n"
        f"要求：每章改编 2-3 场戏，总共约 {len(chapters or []) * 3} 场；"
        f"每场包含 location(地点)、time(白天/夜晚/黄昏/黎明)、emotion(铺垫/爽点/虐点/反转/高潮)、"
        f"summary(场次概要)、beats(节拍数组，3-4 条，每条含 character 角色名、"
        f"dialogue 对白（无对白可空）、narration 旁白/环境、action 动作、emotion 情绪)。\n"
        f"另外输出情绪曲线 emotion_curve（每场一条，含 scene_no、emotion、intensity 1-10）。\n"
        f"严格输出 JSON："
        f'{{"scenes": [{{"scene_no":1,"location":"","time":"","emotion":"","summary":"",'
        f'"beats":[{{"character":"","dialogue":"","narration":"","action":"","emotion":""}}]}}], '
        f'"emotion_curve": [{{"scene_no":1,"emotion":"","intensity":5}}]}}')
    data = _json_call([{"role": "system", "content": _sys("script")},
                       {"role": "user", "content": prompt}],
                      seed=seed, max_tokens=8000)
    scenes = data.get("scenes") or []
    curve = data.get("emotion_curve") or [
        {"scene_no": s["scene_no"], "emotion": s.get("emotion", "铺垫"),
         "intensity": 5} for s in scenes]
    for i, sc in enumerate(scenes):
        sc["scene_no"] = int(sc.get("scene_no", i + 1))
        sc.setdefault("beats", [])
    # 情绪曲线按 scene_no 对齐
    curve = [{"scene_no": int(c["scene_no"]), "emotion": c.get("emotion", "铺垫"),
              "intensity": int(c.get("intensity", 5))} for c in curve]
    if not scenes:
        raise ProviderError("DeepSeek 未返回剧本分场")
    return scenes, curve


# ==================== 分镜设计（M4，真实模式） ====================
def generate_shots(scenes: list[dict], target_count: int, style_id: str,
                   char_names: list[str], seed: int) -> list[dict]:
    scenes_json = json.dumps(scenes[:20], ensure_ascii=False)
    names = "、".join(char_names or ["主角"])
    prompt = (
        f"请把以下剧本分场改编为 {target_count} 个分镜镜头，用于 AI 生成漫画关键帧。\n"
        f"剧本分场（JSON）：\n{scenes_json}\n\n"
        f"出镜角色：{names}。画面风格：{style_id}。\n"
        f"每个镜头要求：shot_no 镜头序号、scene_no 所属场次、shot_type 景别（特写/近景/中景/远景）、"
        f"camera_move 运镜（推/拉/摇/移/固定）、duration 时长（3-6秒）、"
        f"prompt_zh 详细中文画面提示词（描述角色动作/表情/构图/光影/氛围，60-100字，"
        f"角色必须用「{names}」中的名字或『主角』指代）、dialogue 对白（无则空）、"
        f"narration 旁白（无则空）、transition 转场（切/淡入/叠化/白闪）。\n"
        f"严格输出 JSON："
        f'{{"shots": [{{"shot_no":1,"scene_no":1,"shot_type":"近景","camera_move":"推",'
        f'"duration":4.0,"prompt_zh":"","dialogue":"","narration":"","transition":"切"}}]}}')
    data = _json_call([{"role": "system", "content": _sys("shot")},
                       {"role": "user", "content": prompt}],
                      seed=seed, max_tokens=8000)
    shots = data.get("shots") or []
    if not shots:
        raise ProviderError("DeepSeek 未返回分镜表")
    for i, s in enumerate(shots):
        s["shot_no"] = int(s.get("shot_no", i + 1))
        s["scene_no"] = int(s.get("scene_no", 1))
        s["shot_type"] = s.get("shot_type") or "近景"
        s["camera_move"] = s.get("camera_move") or "固定"
        s["duration"] = float(s.get("duration", 4.0))
        s["prompt_zh"] = str(s.get("prompt_zh") or "").strip()
        s.setdefault("dialogue", "")
        s.setdefault("narration", "")
        s.setdefault("transition", "切")
        s["char_ref_ids"] = []   # 由 API 层按角色名映射资产库 ID
        s["style_id"] = style_id
    return shots[:target_count]


# ==================== 需求复述（5.0.1 确认卡，真实模式） ====================
def restate(module: str, params: dict, batch_count: int,
            correction: str | None = None) -> tuple[str, str]:
    """真实 LLM 复述需求；失败时降级到模板复述（不影响确认流程）。"""
    try:
        p = params or {}
        if correction:
            user_txt = (f"用户希望调整已提交的「{module}」生成需求，"
                        f"修正意见：{correction}。请用一句话复述调整后的意图。")
        else:
            user_txt = (f"用户请求执行模块「{module}」，参数：{json.dumps(p, ensure_ascii=False)}，"
                        f"批量数量：{batch_count}。请用一句自然语言复述用户意图，"
                        f"并简短描述预期输出物。")
        content = _chat([{"role": "system",
                          "content": "你是需求理解助手。用简洁中文回答，"
                                     "第一句是复述的意图，第二句是输出物描述。"},
                         {"role": "user", "content": user_txt}],
                        temperature=0.3, max_tokens=300)
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        intent = lines[0] if lines else "AI 生成"
        out = lines[1] if len(lines) > 1 else "AI 生成结果"
        return intent[:120], out[:120]
    except ProviderError as exc:
        logger.warning("DeepSeek 复述失败，降级模板: %s", exc)
        from .mock_llm import restate as _mock_restate
        return _mock_restate(module, params, batch_count, correction)
