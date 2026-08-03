"""分镜设计 API（M4）：剧本 → 镜头语言（纯中文提示词 + [CHAR:x] + 风格 ID）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Project, Shot, User
from ..schemas import ShotGenerateIn, ShotOut, ShotReorderIn, ShotUpdate
from .ai_requests import gate_request

router = APIRouter(tags=["分镜设计"])


@router.get("/projects/{project_id}/shots", response_model=list[ShotOut], summary="分镜表")
def list_shots(project_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    return db.query(Shot).filter(Shot.project_id == project_id).order_by(Shot.order_index).all()


@router.post("/shots/generate", summary="生成分镜（过闸口；批量 ≥20 镜头强制确认）")
def generate_shots(data: ShotGenerateIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    p = db.get(Project, data.project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    params = {"project_id": p.id, "shot_count": data.shot_count,
              "duration_base": data.duration_base, "batch_count": data.shot_count}
    return gate_request(db, user, module="shot", project_id=p.id, params=params,
                        batch_count=data.shot_count, session_id=data.session_id)


@router.put("/shots/{shot_id}", response_model=ShotOut, summary="编辑分镜")
def update_shot(shot_id: int, data: ShotUpdate, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    s = db.get(Shot, shot_id)
    if not s:
        raise HTTPException(status_code=404, detail="分镜不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/shots/{shot_id}", summary="删除分镜（下游资产联动确认由前端承担）")
def delete_shot(shot_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    s = db.get(Shot, shot_id)
    if not s:
        raise HTTPException(status_code=404, detail="分镜不存在")
    db.delete(s)
    db.commit()
    return {"message": "已删除"}


@router.post("/shots/reorder", summary="拖拽排序分镜")
def reorder_shots(data: ShotReorderIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    for idx, sid in enumerate(data.order):
        s = db.get(Shot, sid)
        if s:
            s.order_index = idx
    db.commit()
    return {"message": "已排序"}
