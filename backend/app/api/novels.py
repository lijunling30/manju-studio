"""AI 小说生成 API（M2）：闸口 → 异步生成；支持续写/扩写。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Novel, Project, User
from ..schemas import NovelGenerateIn, NovelOut
from .ai_requests import gate_request

router = APIRouter(tags=["AI 小说生成"])


@router.get("/projects/{project_id}/novel", response_model=Optional[NovelOut], summary="获取项目小说")
def get_novel(project_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    return db.query(Novel).filter(Novel.project_id == project_id).order_by(Novel.id.desc()).first()


@router.post("/novels/generate", summary="生成小说（先过确认闸口，异步执行）")
def generate_novel(data: NovelGenerateIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    p = db.get(Project, data.project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    params = data.model_dump(exclude={"session_id"})
    return gate_request(db, user, module="novel", project_id=p.id, params=params,
                        batch_count=1, session_id=data.session_id)


@router.post("/novels/{novel_id}/continue", summary="续写/扩写小说（过闸口）")
def continue_novel(novel_id: int, chapter_count: int = 4, session_id: str = "",
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    novel = db.get(Novel, novel_id)
    if not novel or novel.status != "completed":
        raise HTTPException(status_code=400, detail="小说不存在或未完成")
    params = {"project_id": novel.project_id, "genre": novel.genre, "mode": "continue",
              "chapter_count": chapter_count, "protagonist": (novel.characters or [{}])[0].get("name", "")}
    return gate_request(db, user, module="novel", project_id=novel.project_id, params=params,
                        batch_count=1, session_id=session_id)
