"""Pydantic Schema：全部 API 请求/响应契约（前后端联调基线）。"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- 鉴权（M10） ----------
class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    phone: str = ""
    plan: str = "personal"


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(ORMModel):
    id: int
    username: str
    phone: str
    role: str
    plan: str
    budget_limit: float
    gate_setting: dict = {}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- 项目管理（M1） ----------
class ProjectCreate(BaseModel):
    name: str
    genre: str = ""
    description: str = ""
    style_id: str = ""
    style_name: str = ""
    target_platform: str = "douyin_9_16"
    budget_limit: float = 0.0
    ip_license: dict = {}


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    genre: Optional[str] = None
    description: Optional[str] = None
    style_id: Optional[str] = None
    style_name: Optional[str] = None
    target_platform: Optional[str] = None
    budget_limit: Optional[float] = None
    ip_license: Optional[dict] = None


class ProjectOut(ORMModel):
    id: int
    user_id: int
    name: str
    genre: str
    description: str
    style_id: str
    style_name: str
    target_platform: str
    status: str
    budget_limit: float
    ip_license: dict
    progress: int
    created_at: datetime


class FlowStep(BaseModel):
    key: str
    label: str
    status: str          # done / current / todo
    detail: str = ""


class ProjectFlowOut(BaseModel):
    project_id: int
    steps: list[FlowStep]


# ---------- 小说（M2） ----------
class NovelGenerateIn(BaseModel):
    project_id: int
    genre: str = ""
    setting: str = ""
    protagonist: str = ""
    chapter_count: int = 8
    mode: str = "full"          # full / continue
    session_id: str = ""


class NovelOut(ORMModel):
    id: int
    project_id: int
    title: str
    genre: str
    setting: dict
    characters: list
    outline: list
    chapters: list
    status: str
    created_at: datetime


# ---------- 剧本（M3） ----------
class ScriptConvertIn(BaseModel):
    project_id: int
    session_id: str = ""


class ScriptUpdate(BaseModel):
    scenes: list
    emotion_curve: list = []


class ScriptOut(ORMModel):
    id: int
    project_id: int
    novel_id: Optional[int]
    title: str
    scenes: list
    emotion_curve: list
    status: str
    created_at: datetime


# ---------- 分镜（M4） ----------
class ShotGenerateIn(BaseModel):
    project_id: int
    shot_count: int = 9
    duration_base: float = 5.0
    session_id: str = ""


class ShotUpdate(BaseModel):
    shot_no: Optional[int] = None
    shot_type: Optional[str] = None
    camera_move: Optional[str] = None
    duration: Optional[float] = None
    prompt_zh: Optional[str] = None
    dialogue: Optional[str] = None
    narration: Optional[str] = None
    transition: Optional[str] = None
    status: Optional[str] = None


class ShotReorderIn(BaseModel):
    order: list[int] = Field(description="按新顺序排列的镜头 ID 列表")


class ShotOut(ORMModel):
    id: int
    project_id: int
    script_id: Optional[int]
    shot_no: int
    scene_no: int
    shot_type: str
    camera_move: str
    duration: float
    prompt_zh: str
    char_ref_ids: list
    style_id: str
    dialogue: str
    narration: str
    transition: str
    status: str
    created_at: datetime


# ---------- 角色资产库（M5） ----------
class LibraryCreate(BaseModel):
    name: str
    desc: str = ""
    project_ids: list[int] = []


class LibraryUpdate(BaseModel):
    name: Optional[str] = None
    desc: Optional[str] = None
    project_ids: Optional[list[int]] = None
    is_shared: Optional[bool] = None
    status: Optional[str] = None


class LibraryOut(ORMModel):
    id: int
    user_id: int
    name: str
    desc: str
    project_ids: list
    is_shared: bool
    status: str
    created_at: datetime


class CharacterCreate(BaseModel):
    library_id: int
    name: str
    desc: str = ""
    appearance: str = ""
    outfit: str = ""
    personality: str = ""
    voice_id: str = ""


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    desc: Optional[str] = None
    appearance: Optional[str] = None
    outfit: Optional[str] = None
    personality: Optional[str] = None
    voice_id: Optional[str] = None
    lora_version: Optional[str] = None


class CharacterImageIn(BaseModel):
    session_id: str = ""


class CharacterOut(ORMModel):
    id: int
    library_id: int
    user_id: int
    name: str
    desc: str
    appearance: str
    outfit: str
    personality: str
    ref_images: list
    expression_set: list
    voice_id: str
    lora_version: str
    status: str
    created_at: datetime


# ---------- 关键帧（M6） ----------
class KeyframeGenerateIn(BaseModel):
    shot_id: int
    count: int = 2
    session_id: str = ""


class KeyframeOut(ORMModel):
    id: int
    shot_id: int
    project_id: int
    image_url: str
    vendor: str
    model: str
    score: dict
    is_approved: bool
    round: int
    cost: float
    created_at: datetime


# ---------- 视频任务（M7） ----------
class VideoTaskCreateIn(BaseModel):
    shot_id: int
    vendor: str = ""
    duration: float = 5.0
    session_id: str = ""
    params: dict = {}


class VideoTaskOut(ORMModel):
    id: int
    shot_id: int
    project_id: int
    vendor: str
    model: str
    status: str
    progress: int
    result_url: str
    preview_url: str
    frames: list
    cost: float
    retry_count: int
    error: str
    created_at: datetime
    updated_at: datetime


# ---------- 配音（M8） ----------
class AudioGenerateIn(BaseModel):
    project_id: int
    shot_ids: list[int] = []
    with_bgm: bool = True
    session_id: str = ""


class AudioAssetOut(ORMModel):
    id: int
    shot_id: int
    project_id: int
    type: str
    asset_url: str
    character_id: int
    voice_id: str
    emotion: str
    text: str
    duration: float
    status: str
    created_at: datetime


# ---------- 成片（M9 / M13） ----------
class RenderIn(BaseModel):
    project_id: int
    episode_no: int = 1
    title: str = ""
    session_id: str = ""


class ExportIn(BaseModel):
    compliance: str = "run"        # run / skip（用户可选，M13）
    platforms: list[str] = ["douyin_9_16", "bilibili_16_9"]
    session_id: str = ""


class FinalVideoOut(ORMModel):
    id: int
    project_id: int
    episode_no: int
    title: str
    url: str
    preview_url: str
    platform_versions: list
    duration: float
    ai_label_burned: bool
    compliance_checked: bool
    audit_status: str
    cost_total: float
    status: str
    created_at: datetime


class AuditReportOut(ORMModel):
    id: int
    final_video_id: int
    project_id: int
    vendor: str
    status: str
    issues: list
    report_url: str
    created_at: datetime


# ---------- 确认闸口（5.0.1） ----------
class AiRequestCreateIn(BaseModel):
    module: str
    project_id: Optional[int] = None
    params: dict = {}
    batch_count: int = 1
    session_id: str = ""


class AiRequestOut(ORMModel):
    id: int
    user_id: int
    project_id: Optional[int]
    module: str
    intent: str
    params_json: dict
    output_desc: str
    cost_estimate: dict
    status: str
    confirm_round: int
    bypass_reason: str
    confirmed_at: Optional[datetime]
    created_at: datetime


class GateSettingIn(BaseModel):
    global_enabled: Optional[bool] = None
    modules_disabled: Optional[list[str]] = None
    high_cost_threshold: Optional[float] = None
    batch_threshold: Optional[int] = None
    session_disabled: Optional[bool] = None


class GateSettingOut(BaseModel):
    global_enabled: bool
    modules_disabled: list
    high_cost_threshold: float
    batch_threshold: int
    session_disabled: bool = False


# ---------- 计费（M10 / A-2） ----------
class CostLogOut(ORMModel):
    id: int
    project_id: int
    module: str
    vendor: str
    model: str
    tokens: int
    duration: float
    count: int
    amount: float
    meta: dict
    created_at: datetime


class CostSummaryOut(BaseModel):
    project_id: int
    total: float
    budget_limit: float
    usage_percent: float
    warn_80: bool
    blocked_100: bool
    by_module: dict
    logs: list[CostLogOut]


# ---------- 任务中心 ----------
class TaskItem(BaseModel):
    id: int
    kind: str              # video / keyframe_batch / audio / render / compliance / novel_generate
    module: str
    ref_id: int
    project_id: int
    status: str
    progress: int
    retry_count: int
    max_retries: int
    error: str
    vendor: str
    preview_url: str
    created_at: datetime
    updated_at: datetime


# ---------- 通用 ----------
class MessageOut(BaseModel):
    message: str
    data: dict[str, Any] = {}


class IdOut(BaseModel):
    id: int
