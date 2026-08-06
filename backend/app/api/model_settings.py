"""模型服务设置 API：用户可自主选择各模块调用的具体模型。

模型偏好存储在 User.model_setting JSON 字段，空值表示使用 .env 默认模型。
任务派发时将用户设置注入任务参数，执行时传给 provider。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import MODEL_CATALOG, DEFAULT_MODELS, settings
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import ModelCatalogOut, ModelSettingIn, ModelSettingOut

router = APIRouter(prefix="/settings", tags=["模型服务设置"])

# model_setting JSON 字段名 → Schema 字段名映射
_FIELD_MAP = {
    "text": "text_model",
    "image": "image_model",
    "video": "video_model",
    "tts": "tts_model",
    "tts_voice": "tts_voice",
}


def _user_setting_to_out(ms: dict) -> ModelSettingOut:
    """将数据库中的 model_setting dict 转为 ModelSettingOut。"""
    return ModelSettingOut(
        text_model=ms.get("text_model", ""),
        image_model=ms.get("image_model", ""),
        video_model=ms.get("video_model", ""),
        tts_model=ms.get("tts_model", ""),
        tts_voice=ms.get("tts_voice", ""),
    )


@router.get("/models", response_model=ModelCatalogOut, summary="查询可选模型目录 + 当前用户设置")
def get_model_catalog(user: User = Depends(get_current_user)):
    ms = user.model_setting or {}
    return ModelCatalogOut(
        catalog=MODEL_CATALOG,
        current=_user_setting_to_out(ms),
        defaults=DEFAULT_MODELS,
    )


@router.put("/models", response_model=ModelSettingOut, summary="更新模型服务设置")
def update_model_settings(data: ModelSettingIn, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    ms = dict(user.model_setting or {})
    # 只覆盖传入的非 None 字段；空字符串表示"恢复默认"
    if data.text_model is not None:
        ms["text_model"] = data.text_model
    if data.image_model is not None:
        ms["image_model"] = data.image_model
    if data.video_model is not None:
        ms["video_model"] = data.video_model
    if data.tts_model is not None:
        ms["tts_model"] = data.tts_model
    if data.tts_voice is not None:
        ms["tts_voice"] = data.tts_voice
    user.model_setting = ms
    db.commit()
    return _user_setting_to_out(ms)
