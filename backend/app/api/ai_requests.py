"""确认闸口 API（5.0.1 ★全局）：所有 AI 调用必经。

流程：用户发起请求 → AI 结构化复述（意图/参数/输出物/成本预估）→ 确认卡
  → 确认 → 执行；修改 → 重新复述（≤3 轮）；放弃/超时 → 取消，零费用。
闸口开关：会话级 / 模块级 / 全局；高成本（≥50 元）或批量（≥20 镜头）强制确认。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core import gate
from ..database import get_db
from ..deps import get_current_user
from ..models import AiRequest, User
from ..schemas import (AiRequestCreateIn, AiRequestOut, GateSettingIn,
                       GateSettingOut, MessageOut)
from .dispatch import dispatch_job

router = APIRouter(prefix="/ai", tags=["确认闸口（全局）"])


def gate_request(db: Session, user: User, *, module: str, project_id: Optional[int],
                 params: dict, batch_count: int, session_id: str = "") -> dict:
    """创建闸口记录；若闸口已放行（bypassed）则直接派发任务。"""
    req, execute_now = gate.open_ai_request(
        db, user, module=module, project_id=project_id, params=params,
        batch_count=batch_count, session_id=session_id or None)
    resp = {"ai_request": AiRequestOut.model_validate(req), "execute_now": execute_now}
    if execute_now:
        try:
            # 闸口记录中已带 project_id，派发时若参数缺失则注入（保证业务侧可用）
            dispatch_params = dict(params)
            dispatch_params.setdefault("project_id", req.project_id)
            resp["dispatch"] = dispatch_job(db, user, module, dispatch_params, req.id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    return resp


@router.post("/requests", summary="发起 AI 请求（进入确认闸口）")
def create_ai_request(data: AiRequestCreateIn, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    return gate_request(db, user, module=data.module, project_id=data.project_id,
                        params=data.params, batch_count=data.batch_count,
                        session_id=data.session_id)


@router.get("/requests", response_model=list[AiRequestOut], summary="查询闸口记录")
def list_requests(status: Optional[str] = None, module: Optional[str] = None,
                  limit: int = 50, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    q = db.query(AiRequest).filter(AiRequest.user_id == user.id)
    if status:
        q = q.filter(AiRequest.status == status)
    if module:
        q = q.filter(AiRequest.module == module)
    return q.order_by(AiRequest.id.desc()).limit(limit).all()


@router.get("/requests/{request_id}", response_model=AiRequestOut, summary="查询单条闸口记录")
def get_ai_request(request_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    req = db.get(AiRequest, request_id)
    if not req or req.user_id != user.id:
        raise HTTPException(status_code=404, detail="记录不存在")
    return req


@router.post("/requests/{request_id}/confirm", response_model=AiRequestOut, summary="确认（放行执行）")
def confirm(request_id: int, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    try:
        return gate.confirm_request(db, user, request_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/requests/{request_id}/execute", summary="闸口确认后执行任务")
def execute(request_id: int, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    req = db.get(AiRequest, request_id)
    if not req or req.user_id != user.id:
        raise HTTPException(status_code=404, detail="记录不存在")
    if req.status not in ("confirmed", "bypassed"):
        raise HTTPException(status_code=400, detail=f"当前状态 {req.status} 不可执行")
    try:
        dispatch_params = dict(req.params_json or {})
        dispatch_params.setdefault("project_id", req.project_id)
        return dispatch_job(db, user, req.module, dispatch_params, req.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/requests/{request_id}/reject", response_model=AiRequestOut, summary="驳回/修改（重新复述，≤3 轮）")
def reject(request_id: int, correction: str = "", user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    try:
        return gate.reject_request(db, user, request_id, correction or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/requests/{request_id}/cancel", response_model=AiRequestOut, summary="放弃（零费用）")
def cancel(request_id: int, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    try:
        return gate.cancel_request(db, user, request_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------- 闸口开关配置（5.0.1） ----------
@router.get("/settings/gate", response_model=GateSettingOut, summary="查询闸口开关状态")
def get_gate_settings(session_id: str = "", user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    gs = user.gate_setting or {}
    return GateSettingOut(
        global_enabled=gs.get("global_enabled", True),
        modules_disabled=gs.get("modules_disabled") or [],
        high_cost_threshold=gs.get("high_cost_threshold", 50.0),
        batch_threshold=gs.get("batch_threshold", 20),
        session_disabled=gate.session_gate_disabled(session_id or None))


@router.put("/settings/gate", response_model=GateSettingOut, summary="更新闸口开关")
def put_gate_settings(data: GateSettingIn, session_id: str = "",
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    gs = dict(user.gate_setting or {})
    if data.global_enabled is not None:
        gs["global_enabled"] = data.global_enabled
    if data.modules_disabled is not None:
        gs["modules_disabled"] = data.modules_disabled
    if data.high_cost_threshold is not None:
        gs["high_cost_threshold"] = data.high_cost_threshold
    if data.batch_threshold is not None:
        gs["batch_threshold"] = data.batch_threshold
    user.gate_setting = gs
    db.commit()
    # 会话级开关独立维护（仅当前会话有效）
    session_disabled = getattr(data, "session_disabled", None)
    if session_disabled is not None and session_id:
        gate.set_session_gate(session_id, session_disabled)
    return GateSettingOut(
        global_enabled=gs.get("global_enabled", True),
        modules_disabled=gs.get("modules_disabled") or [],
        high_cost_threshold=gs.get("high_cost_threshold", 50.0),
        batch_threshold=gs.get("batch_threshold", 20),
        session_disabled=gate.session_gate_disabled(session_id or None))
