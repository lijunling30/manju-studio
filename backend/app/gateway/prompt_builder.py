"""提示词构建模块 —— 集中管理所有 AI 生成的提示词，确保角色/风格/场景一致性。

设计原则：
1. 角色一致性：所有涉及角色的生成（三视图/表情/关键帧）都引用同一份外貌描述
2. 风格一致性：全局风格常量贯穿所有图片生成
3. 场景一致性：关键帧引用场景描述 + 角色描述
4. 输出控制：明确禁止水印/文字/低质量等
"""

# ==================== 全局风格常量 ====================

# 通用画风约束（所有图片生成共享）
STYLE_HINT = (
    "漫画分镜风格，电影级光影，高清细节，构图考究，色彩明快，"
    "符合国漫审美，无文字，无水印，无签名"
)

# 画质增强约束
QUALITY_HINT = "4K 高清，精细线条，专业插画质量，色彩饱满"

# 负面提示（通过正面描述排除）
NEGATIVE_HINT = "无模糊，无变形，无多余肢体，无低质量元素"


# ==================== 角色一致性 ====================

def character_block(name: str, appearance: str, personality: str = "") -> str:
    """角色一致性描述块 —— 所有涉及角色的生成都引用此块。

    确保发型/发色/瞳色/服饰/体型等关键特征在所有生成中保持一致。
    """
    parts = [f"角色名：{name}"]
    if appearance:
        parts.append(f"外貌特征：{appearance}")
    if personality:
        parts.append(f"性格气质：{personality}")
    parts.append("保持角色外观严格一致（发型/发色/瞳色/面部特征/服饰/体型完全不变）")
    return "，".join(parts)


# ==================== 角色 · 三视图 ====================

def character_threeview(name: str, appearance: str, personality: str = "") -> str:
    """角色三视图 prompt：正面/侧面/背面三个角度排列在一张图中。

    用于候选抽卡 —— 每次用不同 seed 产出不同变体，用户从中选择。
    """
    return (
        f"漫画角色三视图参考图（正面、侧面、背面三个角度并排排列），"
        f"{character_block(name, appearance, personality)}，"
        f"全身像，角色设计稿风格，T-pose 站立姿态，纯色浅灰背景，"
        f"三视图比例准确，解剖结构正确，"
        f"{STYLE_HINT}，{QUALITY_HINT}"
    )


# ==================== 角色 · 表情特写 ====================

def character_expression(name: str, appearance: str, emotion: str,
                         personality: str = "") -> str:
    """角色表情 prompt：基于选中三视图的外貌描述生成表情特写。

    使用与选中三视图相同的 seed + 详细外貌描述，增强角色一致性。
    每种情绪生成 2 张候选供用户抽卡选择。
    """
    return (
        f"漫画角色表情特写，情绪：{emotion}，"
        f"{character_block(name, appearance, personality)}，"
        f"面部特写，夸张动画表情，上半身肖像，情绪表达鲜明，"
        f"{STYLE_HINT}，{QUALITY_HINT}"
    )


# ==================== 关键帧 ====================

def keyframe(scene_desc: str, shot_prompt: str, char_names: list[str],
             style_id: str = "") -> str:
    """关键帧 prompt：场景 + 镜头 + 角色 + 风格一致性。"""
    chars = "、".join(char_names) if char_names else "无特定角色"
    return (
        f"漫画分镜关键帧，场景描述：{scene_desc}，"
        f"镜头指示：{shot_prompt}，出场角色：{chars}，"
        f"风格ID：{style_id or 'default'}，"
        f"{STYLE_HINT}，{QUALITY_HINT}"
    )


# ==================== 小说 / 剧本（文本生成） ====================

def novel_system_prompt() -> str:
    """小说生成系统提示：控制输出质量和字数。"""
    return (
        "你是一位资深网文作者，擅长创作引人入胜的中文小说。"
        "要求：1）每章字数充足（2500-3500 字）；"
        "2）角色性格鲜明，对白自然；3）情节紧凑，有悬念；"
        "4）严格按 JSON 格式输出，不要额外解释。"
    )


def script_system_prompt() -> str:
    """剧本生成系统提示：控制结构化输出。"""
    return (
        "你是一位资深编剧，擅长将小说改编为结构化剧本。"
        "要求：1）每个场景包含地点/时间/情绪/概要/节拍；"
        "2）节拍包含角色/对白/旁白/动作/情绪；"
        "3）情绪曲线覆盖全篇；4）严格按 JSON 格式输出。"
    )


def shots_system_prompt() -> str:
    """分镜生成系统提示：控制镜头语言。"""
    return (
        "你是一位资深分镜师，擅长将剧本转化为漫画分镜。"
        "要求：1）每个镜头包含景别/运镜/时长/中文提示词/对白/旁白/转场；"
        "2）提示词纯中文，描述画面内容；3）严格按 JSON 格式输出。"
    )
