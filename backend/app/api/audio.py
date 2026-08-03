"""配音与音效 API（M8）：TTS 对白 + BGM + 音效，音轨分离。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import AudioAsset, Project, User
from ..schemas import AudioAssetOut, AudioGenerateIn
from .ai_requests import gate_request

router = APIRouter(tags=["配音与音效"])


@router.get("/projects/{project_id}/audio", response_model=list[AudioAssetOut], summary="项目音轨")
def list_audio(project_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    return db.query(AudioAsset).filter(AudioAsset.project_id == project_id).all()


@router.post("/audio/generate", summary="生成配音/BGM/音效（过闸口）")
def generate_audio(data: AudioGenerateIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    p = db.get(Project, data.project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    params = {"project_id": p.id, "shot_ids": data.shot_ids, "with_bgm": data.with_bgm}
    batch = max(1, len(data.shot_ids))
    return gate_request(db, user, module="audio_tts", project_id=p.id, params=params,
                        batch_count=batch, session_id=data.session_id)
