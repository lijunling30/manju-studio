"""关键帧生图 API（M6）：批量候选 + AI 评分 + 人工确认 + 再抽一轮。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Keyframe, Project, Shot, User
from ..schemas import KeyframeGenerateIn, KeyframeOut
from .ai_requests import gate_request

router = APIRouter(tags=["关键帧生图"])


@router.get("/shots/{shot_id}/keyframes", response_model=list[KeyframeOut], summary="分镜候选关键帧")
def list_keyframes(shot_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    shot = db.get(Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")
    return db.query(Keyframe).filter(Keyframe.shot_id == shot_id).order_by(Keyframe.id.desc()).all()


@router.post("/keyframes/generate", summary="生成候选关键帧（抽卡，过闸口）")
def generate_keyframes(data: KeyframeGenerateIn, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    shot = db.get(Shot, data.shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")
    last_round = db.query(Keyframe).filter(Keyframe.shot_id == shot.id).count()
    round_no = last_round // data.count + 1 if last_round else 1
    params = {"shot_id": shot.id, "count": data.count, "round": round_no}
    return gate_request(db, user, module="keyframe", project_id=shot.project_id, params=params,
                        batch_count=data.count, session_id=data.session_id)


@router.post("/keyframes/{kf_id}/approve", response_model=KeyframeOut, summary="人工确认关键帧")
def approve_keyframe(kf_id: int, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    kf = db.get(Keyframe, kf_id)
    if not kf:
        raise HTTPException(status_code=404, detail="关键帧不存在")
    shot = db.get(Shot, kf.shot_id)
    # 同一镜头其他候选取消确认
    for other in db.query(Keyframe).filter(Keyframe.shot_id == kf.shot_id).all():
        other.is_approved = False
    kf.is_approved = True
    if shot:
        shot.status = "已确认"
    db.commit()
    db.refresh(kf)
    return kf


@router.post("/shots/{shot_id}/keyframes/reroll", summary="再抽一轮（同参数重生成）")
def reroll(shot_id: int, count: int = 2, session_id: str = "",
           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    shot = db.get(Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")
    rounds = set(k.round for k in db.query(Keyframe).filter(Keyframe.shot_id == shot_id).all())
    round_no = max(rounds, default=0) + 1
    params = {"shot_id": shot.id, "count": count, "round": round_no}
    return gate_request(db, user, module="keyframe", project_id=shot.project_id, params=params,
                        batch_count=count, session_id=session_id)
