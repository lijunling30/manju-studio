"""成本模型（PRD A-2）与预算护栏。

计费维度：文本按 token、图片按张数/分辨率、视频按时长/分辨率、TTS 按字符。
记账粒度：cost_log 表按（项目 × 模块 × 镜头）记录，汇总到项目级/用户级。
预算控制：项目预算上限 → 达 80% 预警 → 达 100% 拦截（生成前）。
"""
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import CostLog, Project

# 单价（元）。MOCK 模式下的参考价格，与「单分钟成片成本 ≤500 元」目标量级一致。
PRICING = {
    "text": {"deepseek_v3": 0.002, "qwen_max": 0.008, "doubao_llm": 0.004, "glm_4": 0.006},   # 元/千token
    "image": {"wanxiang": 0.50, "jimeng": 0.60, "doubao_img": 0.55, "cogview": 0.70},        # 元/张
    "video": {"vidu_q3": 1.20, "seedance_2_0": 0.80, "kling_2_0": 1.50},                     # 元/秒
    "tts": {"doubao_tts": 0.03, "cosyvoice": 0.04, "minimax_voice": 0.05},                   # 元/千字符
    "music": {"sky_music": 0.80, "netease_tianyin": 0.90},                                   # 元/条
    "moderation": {"aliyun_sec": 0.05, "tencent_yuntian": 0.05},                             # 元/次
    "render": {"ffmpeg": 0.05},                                                              # 元/秒（自建 FFmpeg 渲染费）
}

# 模块 → 计费维度
MODULE_DIMENSION = {
    "novel": "text", "script": "text", "shot": "text", "restate": "text",
    "character": "image", "keyframe": "image",
    "video": "video", "audio_tts": "tts", "bgm": "music", "sfx": "text",
    "render": "render", "compliance": "moderation",
}


def unit_price(dimension: str, vendor: str) -> float:
    table = PRICING.get(dimension, {})
    return table.get(vendor) or next(iter(table.values()))


def estimate(module: str, vendor: str, *, tokens: int = 0, duration: float = 0.0,
             count: int = 1, chars: int = 0, seconds: int = 0) -> dict:
    """返回 {low, high, currency, breakdown}。"""
    dim = MODULE_DIMENSION.get(module, "text")
    unit = unit_price(dim, vendor)
    if dim in ("text", "tts", "sfx"):
        qty = (tokens or chars) / 1000.0 or 1.0
    elif dim in ("video", "render"):
        qty = duration or seconds
    else:  # image / music / moderation
        qty = count
    low = round(unit * qty * 0.9, 4)
    high = round(unit * qty * 1.2, 4)
    return {
        "low": low, "high": high, "currency": "CNY",
        "breakdown": {"dimension": dim, "vendor": vendor, "unit_price": unit, "quantity": qty},
    }


def record_cost(db: Session, *, user_id: int, project_id: int, module: str, vendor: str,
                model: str = "", task_id: int = 0, tokens: int = 0, duration: float = 0.0,
                count: int = 1, amount: float = 0.0, meta: Optional[dict] = None) -> CostLog:
    log = CostLog(
        user_id=user_id, project_id=project_id, module=module, vendor=vendor,
        model=model, task_id=task_id, tokens=tokens, duration=duration,
        count=count, amount=round(amount, 4), meta=meta or {},
    )
    db.add(log)
    return log


# ---------- 项目级预算护栏 ----------
def project_spent(db: Session, project_id: int) -> float:
    return float(db.query(func.coalesce(func.sum(CostLog.amount), 0.0))
                 .filter(CostLog.project_id == project_id).scalar() or 0.0)


def check_budget(db: Session, project: Project, est_high: float) -> dict:
    """返回 {ok, blocked, warn_80, spent, usage_percent}；blocked 时调用方不得创建计费任务。"""
    spent = project_spent(db, project.id)
    limit = project.budget_limit or 0.0
    if limit <= 0:
        return {"ok": True, "blocked": False, "warn_80": False, "spent": spent,
                "usage_percent": 0.0, "limit": 0.0}
    percent = spent / limit * 100
    after = (spent + est_high) / limit * 100
    blocked = spent >= limit or after >= 100
    warn = 80 <= percent < 100
    return {"ok": not blocked, "blocked": blocked, "warn_80": warn,
            "spent": spent, "usage_percent": round(percent, 2), "limit": limit}
