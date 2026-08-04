"""项目管理 API（M1）：项目 CRUD、预算、资产聚合视图、9 步流程状态。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core import costs as cost_model
from ..database import get_db
from ..deps import get_current_user
from ..models import (AudioAsset, Character, CharacterLibrary, FinalVideo,
                      Keyframe, Novel, Project, Script, Shot, User, VideoTask)
from ..schemas import (FlowStep, ProjectCreate, ProjectFlowOut, ProjectOut,
                       ProjectUpdate)

router = APIRouter(tags=["项目管理"])

FLOW_DEFS = [
    ("project", "创建项目", "项目已创建"),
    ("novel", "AI 小说生成", "小说章节与角色表"),
    ("script", "剧本结构化", "分场/对白/情绪曲线"),
    ("character", "角色资产库", "三视图/表情集/风格锚点"),
    ("shot", "分镜设计", "镜头语言与中文提示词"),
    ("keyframe", "关键帧抽卡", "候选帧 + AI 评分"),
    ("video", "镜头视频生成", "图生视频片段"),
    ("audio", "配音配乐", "对白/BGM/音效轨"),
    ("final", "成片导出", "合成 + 合规 + AI 标识"),
]


def _project_flow(db: Session, project: Project) -> list[FlowStep]:
    flags = {
        "novel": db.query(Novel).filter(Novel.project_id == project.id,
                                        Novel.status == "completed").first() is not None,
        "script": db.query(Script).filter(Script.project_id == project.id,
                                          Script.status == "completed").first() is not None,
        "shot": db.query(Shot).filter(Shot.project_id == project.id).first() is not None,
        "character": db.query(Character).filter(Character.user_id == project.user_id).first() is not None,
        "keyframe": db.query(Keyframe).filter(Keyframe.project_id == project.id,
                                              Keyframe.is_approved.is_(True)).first() is not None,
        "video": db.query(VideoTask).filter(VideoTask.project_id == project.id,
                                            VideoTask.status == "success").first() is not None,
        "audio": db.query(AudioAsset).filter(AudioAsset.project_id == project.id).first() is not None,
        "final": db.query(FinalVideo).filter(FinalVideo.project_id == project.id,
                                             FinalVideo.status == "completed").first() is not None,
    }
    current_seen = False
    steps = []
    for key, label, detail in FLOW_DEFS:
        if key == "project":
            status, detail = "done", "项目已创建"
        else:
            done = flags.get(key, False)
            if done:
                status = "done"
            else:
                status = "current" if not current_seen else "todo"
                current_seen = current_seen or (status == "current")
                detail = f"待完成：{detail}" if status == "current" else f"未开始：{detail}"
        steps.append(FlowStep(key=key, label=label, status=status, detail=detail))
    return steps


@router.get("/projects", summary="项目列表（含成本统计）")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.query(Project).filter(Project.user_id == user.id,
                                        Project.status != "archived").order_by(Project.id.desc()).all()
    items = []
    for p in projects:
        out = ProjectOut.model_validate(p).model_dump()
        out["spent"] = cost_model.project_spent(db, p.id)
        out["usage_percent"] = round(out["spent"] / p.budget_limit * 100, 1) if p.budget_limit else 0.0
        items.append(out)
    return items


@router.post("/projects", response_model=ProjectOut, summary="创建项目")
def create_project(data: ProjectCreate, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    p = Project(user_id=user.id, **data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/projects/{project_id}", response_model=ProjectOut, summary="项目详情")
def get_project(project_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    return p


@router.get("/projects/{project_id}/flow", response_model=ProjectFlowOut, summary="9 步制作流程状态")
def project_flow(project_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    return ProjectFlowOut(project_id=p.id, steps=_project_flow(db, p))


@router.put("/projects/{project_id}", response_model=ProjectOut, summary="更新项目")
def update_project(project_id: int, data: ProjectUpdate,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/projects/{project_id}", summary="删除项目（二次确认由前端承担）")
def delete_project(project_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    db.delete(p)
    db.commit()
    return {"message": "已删除"}


@router.get("/projects/{project_id}/aggregate", summary="项目资产聚合视图（M1）")
def project_aggregate(project_id: int, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    libs = db.query(CharacterLibrary).filter(CharacterLibrary.user_id == user.id).all()
    chars = db.query(Character).filter(Character.user_id == user.id).all()
    shots = db.query(Shot).filter(Shot.project_id == project_id).count()
    keyframes = db.query(Keyframe).filter(Keyframe.project_id == project_id).count()
    videos = db.query(VideoTask).filter(VideoTask.project_id == project_id).count()
    finals = db.query(FinalVideo).filter(FinalVideo.project_id == project_id).count()
    spent = cost_model.project_spent(db, project_id)
    return {
        "project_id": project_id,
        "counts": {"shots": shots, "keyframes": keyframes, "videos": videos,
                   "final_videos": finals, "characters": len(chars), "libraries": len(libs)},
        "spent": spent,
        "budget_limit": p.budget_limit,
        "libraries": [{"id": l.id, "name": l.name, "project_ids": l.project_ids} for l in libs],
        "flow": [s.model_dump() for s in _project_flow(db, p)],
    }
