"""剧本结构化 API（M3）：小说 → JSON 结构化剧本（scene/dialogue/emotion/action）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Project, Script, User
from ..schemas import ScriptConvertIn, ScriptOut, ScriptUpdate
from .ai_requests import gate_request

router = APIRouter(tags=["剧本结构化"])


@router.get("/projects/{project_id}/script", response_model=ScriptOut | None, summary="获取项目剧本")
def get_script(project_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    return db.query(Script).filter(Script.project_id == project_id).order_by(Script.id.desc()).first()


@router.post("/scripts/convert", summary="小说 → 剧本（过闸口）")
def convert_script(data: ScriptConvertIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    p = db.get(Project, data.project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    return gate_request(db, user, module="script", project_id=p.id,
                        params={"project_id": p.id}, batch_count=1, session_id=data.session_id)


@router.put("/scripts/{script_id}", response_model=ScriptOut, summary="人工修正剧本（增量重结构化）")
def update_script(script_id: int, data: ScriptUpdate,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(Script, script_id)
    if not s:
        raise HTTPException(status_code=404, detail="剧本不存在")
    s.scenes = data.scenes
    s.emotion_curve = data.emotion_curve
    db.commit()
    db.refresh(s)
    return s
