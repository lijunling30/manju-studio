"""数据模型：与 PRD 7.1 / 技术栈说明书 2.5 对齐（v1.3）。"""
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------- 用户与计费（M10） ----------
class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    phone = Column(String(32), default="")
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), default="creator")        # creator / admin
    plan = Column(String(16), default="personal")       # personal / team / enterprise
    budget_limit = Column(Float, default=0.0)           # 0 = 不限制
    gate_setting = Column(JSON, default=dict)           # 确认闸口偏好（全局/模块级）
    model_setting = Column(JSON, default=dict)          # 模型服务偏好（各模块选用的模型，空=用.env默认）
    created_at = Column(DateTime, default=utcnow)


# ---------- 项目管理（M1） ----------
class Project(Base):
    __tablename__ = "project"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), index=True)
    name = Column(String(128), nullable=False)
    genre = Column(String(32), default="")              # 题材
    description = Column(Text, default="")
    style_id = Column(String(32), default="")           # 风格锚点 ID（M4 提示词强制携带）
    style_name = Column(String(64), default="")
    target_platform = Column(String(32), default="douyin_9_16")  # douyin_9_16 / bilibili_16_9
    status = Column(String(16), default="active")       # active / archived
    budget_limit = Column(Float, default=0.0)           # 0 = 不限制
    ip_license = Column(JSON, default=dict)             # {"source":"","authorized":false}（版权校验 M13）
    progress = Column(Integer, default=0)               # 0-100 流程进度
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


# ---------- AI 小说（M2） ----------
class Novel(Base):
    __tablename__ = "novel"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("project.id"), index=True)
    title = Column(String(128), default="")
    genre = Column(String(32), default="")
    setting = Column(JSON, default=dict)                # 世界观设定
    characters = Column(JSON, default=list)             # 角色表 [{name, role, desc}]
    outline = Column(JSON, default=list)                # 章节大纲 [{no,title,summary}]
    chapters = Column(JSON, default=list)               # 章节正文 [{no,title,content}]
    status = Column(String(16), default="draft")        # draft / generating / completed
    created_at = Column(DateTime, default=utcnow)


# ---------- 剧本结构化（M3） ----------
class Script(Base):
    __tablename__ = "script"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("project.id"), index=True)
    novel_id = Column(Integer, ForeignKey("novel.id"))
    title = Column(String(128), default="")
    scenes = Column(JSON, default=list)                 # 分场 [{scene_no,location,time,emotion,summary,beats:[...]}]
    emotion_curve = Column(JSON, default=list)          # 情绪曲线 [{scene_no, emotion(爽点/虐点/反转), intensity}]
    status = Column(String(16), default="draft")        # draft / generating / completed
    created_at = Column(DateTime, default=utcnow)


# ---------- 分镜设计（M4） ----------
class Shot(Base):
    __tablename__ = "shot"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("project.id"), index=True)
    script_id = Column(Integer, ForeignKey("script.id"), index=True)
    shot_no = Column(Integer, default=1)
    scene_no = Column(Integer, default=1)
    shot_type = Column(String(16), default="中景")      # 特写/近景/中景/远景
    camera_move = Column(String(16), default="推")       # 推/拉/摇/移/固定
    duration = Column(Float, default=5.0)
    prompt_zh = Column(Text, default="")                # 纯中文画面提示词（强制携带 [CHAR:x] 与风格 ID）
    char_ref_ids = Column(JSON, default=list)           # [角色ID,...] 强制引用资产库
    style_id = Column(String(32), default="")
    dialogue = Column(Text, default="")
    narration = Column(Text, default="")
    transition = Column(String(16), default="切")
    order_index = Column(Integer, default=0)
    status = Column(String(16), default="待生成")        # 待生成/已确认/生成中/失败
    created_at = Column(DateTime, default=utcnow)


# ---------- 角色资产库（M5） ----------
class CharacterLibrary(Base):
    """人物子库：按项目管理，可被多个项目引用。"""
    __tablename__ = "character_library"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), index=True)
    name = Column(String(128), nullable=False)
    desc = Column(Text, default="")
    project_ids = Column(JSON, default=list)            # 引用的项目 ID 列表
    is_shared = Column(Boolean, default=False)
    status = Column(String(16), default="active")       # active / archived
    created_at = Column(DateTime, default=utcnow)


class Character(Base):
    __tablename__ = "character"
    id = Column(Integer, primary_key=True)
    library_id = Column(Integer, ForeignKey("character_library.id"), index=True)
    user_id = Column(Integer, ForeignKey("user.id"), index=True)
    name = Column(String(64), nullable=False)
    desc = Column(Text, default="")
    appearance = Column(Text, default="")               # 外貌
    outfit = Column(Text, default="")                   # 服饰
    personality = Column(Text, default="")              # 性格
    ref_images = Column(JSON, default=list)             # 候选三视图（抽卡用，用户从中选择）
    approved_ref = Column(Integer, nullable=True)       # 用户选中的三视图索引（None=未选择）
    expression_candidates = Column(JSON, default=list)  # 候选表情图（8 张，用户从中选 4 张）
    expression_set = Column(JSON, default=list)         # 用户确认的表情集（4 张）
    voice_id = Column(String(32), default="")           # 绑定固定音色 ID（M8 配音一致性）
    lora_version = Column(String(16), default="")       # LoRA 版本（P2）
    status = Column(String(16), default="active")
    created_at = Column(DateTime, default=utcnow)


# ---------- 关键帧（M6） ----------
class Keyframe(Base):
    __tablename__ = "keyframe"
    id = Column(Integer, primary_key=True)
    shot_id = Column(Integer, ForeignKey("shot.id"), index=True)
    project_id = Column(Integer, ForeignKey("project.id"), index=True)
    image_url = Column(String(512), default="")
    vendor = Column(String(32), default="")
    model = Column(String(32), default="")
    score = Column(JSON, default=dict)                  # {composition, consistency, clarity, overall}
    is_approved = Column(Boolean, default=False)
    round = Column(Integer, default=1)                  # 抽卡轮次
    cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utcnow)


# ---------- 多镜头视频（M7） ----------
class VideoTask(Base):
    __tablename__ = "video_task"
    id = Column(Integer, primary_key=True)
    shot_id = Column(Integer, ForeignKey("shot.id"), index=True)
    project_id = Column(Integer, ForeignKey("project.id"), index=True)
    vendor = Column(String(32), default="vidu_q3")
    model = Column(String(32), default="Q3")
    duration = Column(Float, default=5.0)       # 秒
    status = Column(String(16), default="queued")       # queued/running/success/failed/retrying/manual_review/cancelled
    progress = Column(Integer, default=0)
    result_url = Column(String(512), default="")
    preview_url = Column(String(512), default="")
    frames = Column(JSON, default=list)
    cost = Column(Float, default=0.0)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error = Column(Text, default="")
    params = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


# ---------- 配音与音效（M8） ----------
class AudioAsset(Base):
    __tablename__ = "audio_asset"
    id = Column(Integer, primary_key=True)
    shot_id = Column(Integer, ForeignKey("shot.id"), index=True)
    project_id = Column(Integer, ForeignKey("project.id"), index=True)
    type = Column(String(8), default="voice")           # voice / bgm / sfx
    asset_url = Column(String(512), default="")
    character_id = Column(Integer, default=0)
    voice_id = Column(String(32), default="")
    emotion = Column(String(16), default="中性")
    text = Column(Text, default="")
    duration = Column(Float, default=2.0)
    status = Column(String(16), default="completed")
    created_at = Column(DateTime, default=utcnow)


# ---------- 成片（M9） ----------
class FinalVideo(Base):
    __tablename__ = "final_video"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("project.id"), index=True)
    episode_no = Column(Integer, default=1)
    title = Column(String(128), default="")
    url = Column(String(512), default="")
    preview_url = Column(String(512), default="")
    platform_versions = Column(JSON, default=list)      # [{platform, spec, url}]
    duration = Column(Float, default=0.0)
    ai_label_burned = Column(Boolean, default=False)    # AI 生成标识（强制项，无开关）
    compliance_checked = Column(Boolean, default=False)
    audit_status = Column(String(16), default="none")   # none/pending/pass/reject/skip
    cost_total = Column(Float, default=0.0)
    status = Column(String(16), default="draft")        # draft/rendering/completed
    created_at = Column(DateTime, default=utcnow)


# ---------- 成本记账（A-2） ----------
class CostLog(Base):
    __tablename__ = "cost_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), index=True)
    project_id = Column(Integer, ForeignKey("project.id"), index=True)
    module = Column(String(24), default="")             # novel/script/shot/character/keyframe/video/audio/render/compliance
    vendor = Column(String(32), default="")
    model = Column(String(32), default="")
    task_id = Column(Integer, default=0)
    tokens = Column(Integer, default=0)
    duration = Column(Float, default=0.0)
    count = Column(Integer, default=1)
    amount = Column(Float, default=0.0)
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)


# ---------- 确认闸口（5.0.1） ----------
class AiRequest(Base):
    __tablename__ = "ai_request"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), index=True)
    project_id = Column(Integer, ForeignKey("project.id"), index=True)
    module = Column(String(24), default="")
    intent = Column(Text, default="")                   # AI 结构化复述
    params_json = Column(JSON, default=dict)
    output_desc = Column(Text, default="")
    cost_estimate = Column(JSON, default=dict)          # {low, high, currency, breakdown}
    status = Column(String(16), default="draft")        # draft/confirmed/rejected/bypassed/timeout/cancelled
    confirm_round = Column(Integer, default=1)
    bypass_reason = Column(String(64), default="")
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


# ---------- 合规模块 M13 ----------
class AuditReport(Base):
    __tablename__ = "audit_report"
    id = Column(Integer, primary_key=True)
    final_video_id = Column(Integer, ForeignKey("final_video.id"), index=True)
    project_id = Column(Integer, ForeignKey("project.id"), index=True)
    vendor = Column(String(32), default="aliyun_sec")
    status = Column(String(16), default="pending")      # pending/pass/reject
    issues = Column(JSON, default=list)
    report_url = Column(String(512), default="")
    raw = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)


# ---------- 通用异步任务（L3 任务编排） ----------
class TaskRecord(Base):
    """非视频类异步任务（关键帧批量/配音/渲染/合规/小说生成）统一状态机。"""
    __tablename__ = "task_record"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), index=True)
    project_id = Column(Integer, ForeignKey("project.id"), index=True)
    module = Column(String(24), default="")
    kind = Column(String(24), default="")               # keyframe_batch/audio/render/compliance/novel_generate
    ref_id = Column(Integer, default=0)                 # 关联业务对象 ID
    status = Column(String(16), default="queued")       # queued/running/success/failed/retrying/manual_review/cancelled
    progress = Column(Integer, default=0)
    error = Column(Text, default="")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    result = Column(JSON, default=dict)
    params = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
