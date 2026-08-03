"""成片 API（M9 剪辑与质检 / M13 合规检验）。

强制项（无开关）：所有导出成片必须携带 AI 生成标识（显式角标 + 元数据水印），
标识缺失禁止导出。
可选模块（M13）：导出前由用户自选「执行合规检验 / 跳过（仅带 AI 标识）」。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import AuditReport, FinalVideo, Project, User
from ..schemas import (AuditReportOut, ExportIn, FinalVideoOut, RenderIn)
from .ai_requests import gate_request

router = APIRouter(tags=["成片与合规"])


@router.get("/projects/{project_id}/final-videos", response_model=list[FinalVideoOut], summary="项目成片列表")
def list_final_videos(project_id: int, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    return db.query(FinalVideo).filter(FinalVideo.project_id == project_id).order_by(FinalVideo.id.desc()).all()


@router.get("/final-videos/{fv_id}", response_model=FinalVideoOut, summary="成片详情")
def get_final_video(fv_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    fv = db.get(FinalVideo, fv_id)
    if not fv:
        raise HTTPException(status_code=404, detail="成片不存在")
    return fv


@router.post("/final-videos/render", summary="渲染合成成片（过闸口；强制携带 AI 标识）")
def render_final(data: RenderIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    p = db.get(Project, data.project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    params = {"project_id": p.id, "episode_no": data.episode_no, "title": data.title}
    return gate_request(db, user, module="render", project_id=p.id, params=params,
                        batch_count=1, session_id=data.session_id)


@router.post("/final-videos/{fv_id}/export",
             summary="导出成片（合规自选 + AI 标识强制）")
def export_final(fv_id: int, data: ExportIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    fv = db.get(FinalVideo, fv_id)
    if not fv:
        raise HTTPException(status_code=404, detail="成片不存在")
    # ★强制项校验：AI 生成标识缺失禁止导出
    if not fv.ai_label_burned:
        raise HTTPException(status_code=400, detail="AI 生成标识未烧录，禁止导出（合规强制项）")
    if fv.status != "completed":
        raise HTTPException(status_code=400, detail="成片尚未完成渲染")

    platforms = data.platforms or ["douyin_9_16", "bilibili_16_9"]
    fv.platform_versions = [
        {"platform": p, "spec": {"douyin_9_16": "9:16 · 1080×1920",
                                 "bilibili_16_9": "16:9 · 1920×1080"}.get(p, ""),
         "url": fv.preview_url, "exported": True}
        for p in platforms
    ]
    # M13：用户自选合规检验（返回闸口响应：draft 待确认 / bypassed 直接派发）
    if data.compliance == "run":
        db.commit()
        return gate_request(db, user, module="compliance", project_id=fv.project_id,
                            params={"final_video_id": fv.id},
                            batch_count=1, session_id=data.session_id)
    fv.compliance_checked = False
    fv.audit_status = "skip"
    db.commit()
    db.refresh(fv)
    return fv


@router.post("/final-videos/{fv_id}/compliance", summary="补做合规检验（无需重新渲染）")
def run_compliance(fv_id: int, session_id: str = "", user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    fv = db.get(FinalVideo, fv_id)
    if not fv:
        raise HTTPException(status_code=404, detail="成片不存在")
    return gate_request(db, user, module="compliance", project_id=fv.project_id,
                        params={"final_video_id": fv.id},
                        batch_count=1, session_id=session_id)


@router.get("/final-videos/{fv_id}/audit", response_model=list[AuditReportOut], summary="审核报告列表")
def audit_reports(fv_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    fv = db.get(FinalVideo, fv_id)
    if not fv:
        raise HTTPException(status_code=404, detail="成片不存在")
    return db.query(AuditReport).filter(AuditReport.final_video_id == fv_id).order_by(AuditReport.id.desc()).all()
