"""模拟 LLM 厂商（DeepSeek-V3 等）。

MOCK_MODE 下用确定性模板 + 随机种子生成结构合理的
小说大纲/正文、剧本分场、分镜表、需求复述，用于演示全流程。
真实接入时替换为 DeepSeek / 通义千问 / 豆包的 HTTP 调用。
"""
import random

# ---------- 题材模板 ----------
GENRE_PATTERNS = {
    "都市": {
        "scene_pool": ["写字楼天台", "深夜便利店", "高档餐厅", "地铁末班车", "老城区出租屋"],
        "setting": "现代都市，商业竞争与人间冷暖交织",
        "opening": "清晨的写字楼玻璃幕墙反射着第一缕阳光，",
        "twist": "一封匿名邮件让局势骤然反转",
    },
    "玄幻": {
        "scene_pool": ["云雾缭绕的山门", "上古秘境", "边境古城", "灵泉洞穴", "宗门大殿"],
        "setting": "灵气复苏的东方玄幻世界，宗门林立，妖兽横行",
        "opening": "山门外雷云翻涌，数百年未现的天地异象惊动了闭关的诸位长老，",
        "twist": "一枚残破的古印显露出惊世传承",
    },
    "末世": {
        "scene_pool": ["废弃超市", "末日公路", "地下避难所", "孤岛灯塔", "废墟楼顶"],
        "setting": "末日降临，丧尸横行，幸存者在废土中争夺资源与生机",
        "opening": "警报声响彻城市的最后一夜，",
        "twist": "人类文明的幸存者内部出现了叛徒",
    },
    "古风": {
        "scene_pool": ["长安街市", "深宫庭院", "大漠孤城", "江南水乡", "山间客栈"],
        "setting": "古代王朝更迭，庙堂与江湖暗流涌动",
        "opening": "长安城的第一场雪落时，",
        "twist": "一封密诏将主角卷入夺嫡之局",
    },
    "科幻": {
        "scene_pool": ["星际飞船驾驶舱", "火星殖民基地", "赛博城市雨巷", "量子实验室", "太空站"],
        "setting": "近未来太空时代，人类文明与未知文明交锋",
        "opening": "深空探测器传回的一段异常信号，",
        "twist": "人类赖以生存的母星数据被悄然篡改",
    },
}
DEFAULT_PATTERN = {
    "scene_pool": ["街角咖啡馆", "城市公园", "旧书店", "车站月台", "江边步道"],
    "setting": "一个充满机遇与挑战的世界",
    "opening": "故事开始的那个下午，",
    "twist": "一个不起眼的细节改变了所有人的命运",
}

PLOT_STAGES = [
    ("第{no}章 {title}", "主角初入局，埋下悬念伏笔"),
    ("第{no}章 {title}", "矛盾升级，主角被迫迎战"),
    ("第{no}章 {title}", "真相初现，阵营立场浮出水面"),
    ("第{no}章 {title}", "反转降临，局势急转直下"),
    ("第{no}章 {title}", "高潮对决，旧秩序被打破"),
]

PARAGRAPH_TEMPLATES = [
    "{protagonist}站在{place}，望着眼前的一切，心中那股不安终于有了答案。",
    "就在此时，{twist}。远处的喧哗声由远及近，{protagonist}握紧了拳头。",
    "「这不可能是巧合。」{protagonist}低声说道，目光扫过在场的每一个人。",
    "风掠过{place}，卷起细碎的尘埃。{protagonist}想起出发前{guardian}的叮嘱，脚步却未停。",
    "夜色渐深，{place}陷入一片寂静。唯有{protagonist}的呼吸声，与心跳声交织在一起。",
    "消息像野火一样传开。{protagonist}知道，属于他的时代，就要来了。",
]

SHOT_TYPES = ["特写", "近景", "中景", "远景"]
CAMERA_MOVES = ["推", "拉", "摇", "移", "固定"]
TRANSITIONS = ["切", "淡入", "叠化", "白闪"]
EMOTIONS = ["铺垫", "爽点", "虐点", "反转", "高潮"]


def _pattern(genre: str) -> dict:
    return GENRE_PATTERNS.get(genre, DEFAULT_PATTERN)


def _titles(chapter_count: int, seed: int) -> list[str]:
    rnd = random.Random(seed)
    pool = ["初入风云", "暗流涌动", "绝地反击", "真相浮现", "命运转折",
            "孤注一掷", "巅峰对决", "黎明之前", "尘埃落定", "新的序章"]
    rnd.shuffle(pool)
    return [pool[i % len(pool)] for i in range(chapter_count)]


# ---------- 需求复述（5.0.1 确认卡内容） ----------
def restate(module: str, params: dict, batch_count: int, correction: str | None = None) -> tuple[str, str]:
    if correction:
        return (f"已根据您的反馈调整：{correction}", "根据修正意见重新生成，其他参数保持不变")
    p = params or {}
    if module == "novel":
        intent = (f"为「{p.get('genre') or '自定义'}」题材创作 {p.get('chapter_count', 8)} 章小说"
                  f"（世界观：{p.get('setting') or '待定'}；主角：{p.get('protagonist') or '待定'}）")
        out = "章节目录 + 章节正文 + 角色表 + 设定集"
    elif module == "script":
        intent = f"将小说《{p.get('title', '')}》转换为结构化剧本（分场/对白/旁白/情绪标注）"
        out = "JSON 结构化剧本：scene/character/dialogue/narration/emotion/action"
    elif module == "shot":
        intent = f"将剧本拆解为 {batch_count} 个分镜镜头（中文画面提示词 + 角色引用 [CHAR:x] + 风格 ID）"
        out = "分镜表：镜头号/景别/运镜/时长/中文提示词/对白/转场"
    elif module == "character":
        intent = f"为角色「{p.get('name', '')}」生成三视图参考图（外貌：{p.get('appearance') or '待定'}）"
        out = "正面/侧面/背面三张参考图（可用于下游一致性绑定）"
    elif module == "keyframe":
        intent = f"为分镜 #{p.get('shot_no', '')} 生成 {p.get('count', 2)} 张候选关键帧并 AI 自动评分"
        out = "候选关键帧（构图/一致性/清晰度评分）"
    elif module == "video":
        intent = f"为分镜 #{p.get('shot_no', '')} 生成 {p.get('duration', 5)} 秒镜头视频（厂商：{p.get('vendor', 'Vidu Q3')}）"
        out = "4-10 秒 mp4 竖屏/横屏视频片段"
    elif module == "audio_tts":
        intent = f"为角色「{p.get('name', '')}」的台词生成配音（音色：{p.get('voice_id') or '默认'}；情绪：{p.get('emotion') or '中性'}）"
        out = "角色对白音频轨（按镜头时间轴对齐）"
    elif module == "bgm":
        intent = f"为项目生成情绪「{p.get('emotion') or '中性'}」的背景音乐"
        out = "BGM 音频轨"
    elif module == "sfx":
        intent = f"生成音效：{p.get('text', '')}"
        out = "音效音频轨"
    elif module == "render":
        intent = f"将 {p.get('shot_count', 0)} 个镜头合成成片（平台规格：{p.get('platforms', '抖音 9:16')}；强制携带 AI 生成标识）"
        out = "完整成片 mp4 + 平台规格版本（显式角标 + 元数据水印）"
    elif module == "compliance":
        intent = f"对成片《{p.get('title', '')}》执行合规检验（内容安全审核，机器审核 + 人工复核）"
        out = "结构化审核报告（通过/驳回 + 违规定位）"
    else:
        intent = f"执行模块「{module}」的 AI 生成"
        out = "AI 生成结果"
    return intent, out


# ---------- 小说生成（M2） ----------
def generate_novel_outline(genre: str, setting: str, protagonist: str, chapter_count: int, seed: int) -> list[dict]:
    rnd = random.Random(seed)
    pattern = _pattern(genre)
    titles = _titles(chapter_count, seed)
    outline = []
    for i in range(chapter_count):
        stage = PLOT_STAGES[i % len(PLOT_STAGES)]
        title = f"第{i + 1}章 {titles[i]}"
        summary = stage[1].replace("{no}", str(i + 1)).replace("{title}", titles[i])
        if i == 0:
            summary = pattern["opening"] + summary
        elif i == chapter_count - 1:
            summary = pattern["twist"] + "，主角迎来最终抉择，" + summary
        else:
            summary = f"{protagonist}在{pattern['scene_pool'][rnd.randrange(len(pattern['scene_pool']))]}的行动" + summary
        outline.append({"no": i + 1, "title": title, "summary": summary})
    return outline


def generate_chapter(chapter: dict, genre: str, setting: str, protagonist: str, seed: int) -> str:
    rnd = random.Random(seed * 131 + chapter["no"])
    pattern = _pattern(genre)
    place = rnd.choice(pattern["scene_pool"])
    paragraphs = rnd.sample(PARAGRAPH_TEMPLATES, k=min(4, len(PARAGRAPH_TEMPLATES)))
    parts = [f"{chapter['title']}\n"]
    parts.append(pattern["opening"] + f"{protagonist}踏上了新的征程，而{setting}的真相远比他想象的复杂。\n")
    for t in paragraphs:
        parts.append(t.format(protagonist=protagonist, place=place,
                              twist=pattern["twist"], guardian="师父"))
    if chapter["no"] == 1:
        parts.append(f"「{protagonist}，记住这个名字——」远方的声音消散在风中。\n")
    return "\n".join(parts)


def generate_characters(protagonist: str, genre: str, seed: int) -> list[dict]:
    rnd = random.Random(seed + 7)
    names = ["苏晴", "顾长风", "小满", "阿昭", "老周"]
    roles = ["主角", "对手", "挚友", "关键配角", "神秘人物"]
    chars = [{"name": protagonist, "role": "主角",
              "desc": f"《{genre}》故事的核心人物，性格坚韧，善于在绝境中找到出路"}]
    for i in range(min(4, len(names))):
        chars.append({"name": names[i], "role": roles[i],
                      "desc": f"{roles[i]}，{rnd.choice(['外冷内热', '心机深沉', '古道热肠', '天真烂漫'])}"})
    return chars


# ---------- 剧本结构化（M3） ----------
def generate_scenes(novel_title: str, chapters: list[dict], seed: int) -> tuple[list[dict], list[dict]]:
    rnd = random.Random(seed)
    pattern = _pattern("都市")  # 场景池通用
    scenes, curve = [], []
    scene_no = 1
    for ch in chapters:
        n_scenes = rnd.randint(2, 3)
        ch_summary = ch.get("summary") or ch.get("title", "")
        for _ in range(n_scenes):
            emotion = rnd.choice(EMOTIONS)
            location = rnd.choice(pattern["scene_pool"])
            summary = f"{ch_summary}（场次：{location}）"
            beats = []
            for b in range(rnd.randint(3, 4)):
                beats.append({
                    "character": rnd.choice(["主角", "对手", "配角"]),
                    "dialogue": rnd.choice([
                        "「你到底想怎样？」", "「记住，活下去才有以后。」",
                        "「这件事，没这么简单。」", "「跟我走，现在！」",
                        "「从今天起，局面不一样了。」"]),
                    "narration": rnd.choice([
                        "风起，衣角猎猎作响。", "短暂的沉默，空气凝滞。",
                        "脚步声由远及近。", "灯光忽明忽暗。"]),
                    "action": rnd.choice(["转身离开", "缓缓拔出武器", "望向远方", "握紧拳头"]),
                    "emotion": rnd.choice(["紧张", "决绝", "释然", "愤怒", "隐忍"]),
                })
            scenes.append({
                "scene_no": scene_no, "location": location,
                "time": rnd.choice(["白天", "夜晚", "黄昏", "黎明"]),
                "emotion": emotion, "summary": summary, "beats": beats,
            })
            curve.append({"scene_no": scene_no, "emotion": emotion, "intensity": rnd.randint(3, 10)})
            scene_no += 1
    return scenes, curve


# ---------- 分镜设计（M4） ----------
def generate_shots(scenes: list[dict], target_count: int, style_id: str,
                   char_names: list[str], seed: int) -> list[dict]:
    rnd = random.Random(seed)
    shots = []
    per_scene = max(1, round(target_count / max(1, len(scenes))))
    for sc in scenes:
        for i in range(per_scene):
            char = char_names[rnd.randrange(len(char_names))] if char_names else "主角"
            beat = (sc.get("beats") or [{}])[i % max(1, len(sc.get("beats") or [{}]))]
            prompt = (f"{rnd.choice(SHOT_TYPES)}镜头，{rnd.choice(CAMERA_MOVES)}镜头，"
                      f"{sc.get('location', '场景')}内，{char}{beat.get('action', '凝视前方')}，"
                      f"情绪：{beat.get('emotion', '中性')}，电影级光影，高清细节")
            if style_id:
                prompt += f"，风格 {style_id}"
            shots.append({
                "shot_no": len(shots) + 1,
                "scene_no": sc.get("scene_no", 1),
                "shot_type": rnd.choice(SHOT_TYPES),
                "camera_move": rnd.choice(CAMERA_MOVES),
                "duration": rnd.choice([3.0, 4.0, 5.0, 6.0]),
                "prompt_zh": prompt,
                "char_ref_ids": [],  # 由 API 层按角色名映射到资产库 ID
                "style_id": style_id,
                "dialogue": beat.get("dialogue", ""),
                "narration": beat.get("narration", ""),
                "transition": rnd.choice(TRANSITIONS),
            })
    return shots[:target_count]   # 精确控制镜头数（场景数×每场镜头数可能超量）


def estimate_tokens(module: str, params: dict) -> int:
    p = params or {}
    if module == "novel":
        return p.get("chapter_count", 8) * 2500
    if module == "script":
        return 8000
    if module == "shot":
        return p.get("batch_count", 10) * 600
    return 600
