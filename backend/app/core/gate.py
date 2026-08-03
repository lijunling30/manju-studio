"""确认闸口（PRD 5.0.1 / A-4）核心逻辑。

原则：任何 AI 生成/编辑/续写请求，必须先结构化复述需求并预估成本，
经用户确认后才执行；未确认前不调用任何付费接口、不产生算力消耗。

闸口开关：会话级（内存）/ 模块级（user.gate_setting）/ 全局（user.gate_setting）。
成本护栏：单次 ≥50 元 或 批量 ≥20 镜头时即使闸口关闭仍强制确认。
超时：GATE_TIMEOUT_SECONDS 未确认自动置为 timeout，不产生费用。
"""
import threading

from sqlalchemy.orm import Session

from ..config import settings
from ..gateway.router import gateway
from ..models import AiRequest, User, utcnow


class GateDecision:
    def __init__(self, required: bool, reason: str):
        self.required = required
        self.reason = reason


# ---------- 会话级闸口状态（仅当前浏览器会话有效，刷新/重新登录默认恢复开启） ----------
_session_lock = threading.Lock()
_session_state: dict[str, dict] = {}   # {session_id: {"disabled": bool}}


def set_session_gate(session_id: str, disabled: bool) -> None:
    if not session_id:
        return
    with _session_lock:
        _session_state[session_id] = {"disabled": disabled}


def session_gate_disabled(session_id: str | None) -> bool:
    if not session_id:
        return False
    with _session_lock:
        return bool(_session_state.get(session_id, {}).get("disabled"))


def evaluate_gate(user: User, module: str, cost_estimate: dict,
                  batch_count: int, session_id: str | None = None) -> GateDecision:
    # 成本护栏：高成本 / 批量任务即使关闭闸口仍强制确认
    if (cost_estimate.get("high") or 0) >= settings.GATE_HIGH_COST_THRESHOLD:
        return GateDecision(required=True, reason="high_cost_guardrail")
    if batch_count >= settings.GATE_BATCH_THRESHOLD:
        return GateDecision(required=True, reason="batch_guardrail")

    gs = user.gate_setting or {}
    if not gs.get("global_enabled", True):
        return GateDecision(required=False, reason="global_disabled")
    if module in (gs.get("modules_disabled") or []):
        return GateDecision(required=False, reason="module_disabled")
    if session_gate_disabled(session_id):
        return GateDecision(required=False, reason="session_disabled")
    return GateDecision(required=True, reason="default")


def open_ai_request(db: Session, user: User, *, module: str, project_id: int | None,
                    params: dict, batch_count: int = 1,
                    session_id: str | None = None) -> tuple[AiRequest, bool]:
    """创建闸口记录。

    返回 (ai_request, execute_now)：
    - execute_now=True  → 闸口已放行（bypassed），调用方可直接执行任务；
    - execute_now=False → 处于 draft，等待用户 confirm 后再执行。
    """
    estimate = gateway.estimate(module, params)
    intent, output_desc = gateway.restate(module, params, batch_count)
    decision = evaluate_gate(user, module, estimate, batch_count, session_id)

    req = AiRequest(
        user_id=user.id, project_id=project_id, module=module,
        intent=intent, params_json=params, output_desc=output_desc,
        cost_estimate=estimate, status="bypassed" if not decision.required else "draft",
        bypass_reason=decision.reason, confirm_round=1,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req, (not decision.required)


def confirm_request(db: Session, user: User, request_id: int) -> AiRequest:
    req = db.get(AiRequest, request_id)
    if not req or req.user_id != user.id:
        raise ValueError("ai_request_not_found")
    if req.status != "draft":
        raise ValueError(f"ai_request_invalid_status:{req.status}")
    req.status = "confirmed"
    req.confirmed_at = utcnow()
    db.commit()
    db.refresh(req)
    return req


def reject_request(db: Session, user: User, request_id: int, correction: str | None) -> AiRequest:
    req = db.get(AiRequest, request_id)
    if not req or req.user_id != user.id:
        raise ValueError("ai_request_not_found")
    if req.status != "draft":
        raise ValueError(f"ai_request_invalid_status:{req.status}")
    if req.confirm_round >= settings.GATE_MAX_CONFIRM_ROUNDS:
        # 修改复述达到上限（3 轮），转人工引导
        req.status = "cancelled"
        req.bypass_reason = "rounds_exceeded_manual"
    else:
        # 重新复述（基于用户修正反馈）
        params = dict(req.params_json or {})
        if correction:
            params["user_correction"] = correction
        req.intent, req.output_desc = gateway.restate(req.module, params, 1, correction=correction)
        req.cost_estimate = gateway.estimate(req.module, params)
        req.params_json = params
        req.confirm_round += 1
        req.status = "draft"
    db.commit()
    db.refresh(req)
    return req


def cancel_request(db: Session, user: User, request_id: int) -> AiRequest:
    req = db.get(AiRequest, request_id)
    if not req or req.user_id != user.id:
        raise ValueError("ai_request_not_found")
    if req.status == "draft":
        req.status = "cancelled"
    db.commit()
    db.refresh(req)
    return req


def sweep_timeouts(db: Session) -> int:
    """将超时（60s）未确认的 draft 置为 timeout——默认不执行、不产生费用。"""
    cutoff = utcnow().timestamp() - settings.GATE_TIMEOUT_SECONDS
    expired = db.query(AiRequest).filter(
        AiRequest.status == "draft",
    ).all()
    n = 0
    for r in expired:
        if r.created_at.timestamp() < cutoff:
            r.status = "timeout"
            n += 1
    if n:
        db.commit()
    return n
