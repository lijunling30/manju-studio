"""多镜头视频生成 API（M7 ★核心引擎）：异步任务全生命周期 + 失败重试/降级。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Project, Shot, User, VideoTask
from ..schemas import VideoTaskCreateIn, VideoTaskOut
from .ai_requests import gate_request

router = APIRouter(tags=["多镜头视频生成"])


@router.get("/shots/{shot_id}/video-tasks", response_model=list[VideoTaskOut], summary="镜头的视频任务")
def list_video_tasks(shot_id: int, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    shot = db.get(Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")
    return db.query(VideoTask).filter(VideoTask.shot_id == shot_id).order_by(VideoTask.id.desc()).all()


@router.post("/video-tasks", summary="提交镜头视频生成（过闸口；异步执行）")
def create_video_task(data: VideoTaskCreateIn, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    shot = db.get(Shot, data.shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")
    params = {"shot_id": shot.id, "duration": data.duration,
              "vendor": data.vendor, **data.params}
    return gate_request(db, user, module="video", project_id=shot.project_id, params=params,
                        batch_count=1, session_id=data.session_id)


@router.get("/video-tasks/{task_id}", response_model=VideoTaskOut, summary="查询视频任务（轮询）")
def get_video_task(task_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    vt = db.get(VideoTask, task_id)
    if not vt:
        raise HTTPException(status_code=404, detail="任务不存在")
    return vt


@router.post("/video-tasks/{task_id}/cancel", response_model=VideoTaskOut, summary="取消任务")
def cancel_video_task(task_id: int, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    vt = db.get(VideoTask, task_id)
    if not vt:
        raise HTTPException(status_code=404, detail="任务不存在")
    if vt.status in ("queued", "running", "retrying"):
        vt.status = "cancelled"
        vt.error = "用户取消"
        db.commit()
    db.refresh(vt)
    return vt


@router.post("/video-tasks/{task_id}/retry", response_model=VideoTaskOut,
             summary="人工重试 / 换厂商重跑")
def retry_video_task(task_id: int, vendor: str = "", user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    vt = db.get(VideoTask, task_id)
    if not vt:
        raise HTTPException(status_code=404, detail="任务不存在")
    if vendor:
        vt.vendor = vendor
    vt.retry_count = 0
    vt.error = ""
    vt.status = "queued"
    vt.progress = 0
    db.commit()
    db.refresh(vt)
    return vt
