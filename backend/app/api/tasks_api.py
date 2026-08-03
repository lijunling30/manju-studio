"""全局任务中心 API（P-12）：合并视频任务 + 通用任务，实时轮询。"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Project, TaskRecord, User, VideoTask
from ..schemas import TaskItem

router = APIRouter(tags=["全局任务中心"])


@router.get("/tasks", response_model=list[TaskItem], summary="任务中心（轮询）")
def list_tasks(status: Optional[str] = None, limit: int = 30,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items: list[TaskItem] = []
    vt_q = db.query(VideoTask).join(Project, VideoTask.project_id == Project.id).filter(
        Project.user_id == user.id)
    if status:
        vt_q = vt_q.filter(VideoTask.status == status)
    for vt in vt_q.order_by(VideoTask.id.desc()).limit(limit).all():
        items.append(TaskItem(id=vt.id, kind="video", module="video", ref_id=vt.shot_id,
                              project_id=vt.project_id, status=vt.status, progress=vt.progress,
                              retry_count=vt.retry_count, max_retries=vt.max_retries,
                              error=vt.error, vendor=vt.vendor, preview_url=vt.preview_url,
                              created_at=vt.created_at, updated_at=vt.updated_at))

    tr_q = db.query(TaskRecord).join(Project, TaskRecord.project_id == Project.id).filter(
        Project.user_id == user.id)
    if status:
        tr_q = tr_q.filter(TaskRecord.status == status)
    for tr in tr_q.order_by(TaskRecord.id.desc()).limit(limit).all():
        items.append(TaskItem(id=tr.id, kind=tr.kind, module=tr.module, ref_id=tr.ref_id,
                              project_id=tr.project_id, status=tr.status, progress=tr.progress,
                              retry_count=tr.retry_count, max_retries=tr.max_retries,
                              error=tr.error, vendor="", preview_url="",
                              created_at=tr.created_at, updated_at=tr.updated_at))

    items.sort(key=lambda t: t.updated_at, reverse=True)
    return items[:limit]
