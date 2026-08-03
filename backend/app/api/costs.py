"""计费与成本 API（M10 / A-2）：项目账单、用户汇总、预算设置。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import costs as cost_model
from ..database import get_db
from ..deps import get_current_user
from ..models import CostLog, Project, User
from ..schemas import CostLogOut, CostSummaryOut

router = APIRouter(tags=["计费与成本"])


@router.get("/projects/{project_id}/costs", response_model=CostSummaryOut, summary="项目成本汇总")
def project_costs(project_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    logs = db.query(CostLog).filter(CostLog.project_id == project_id).order_by(CostLog.id.desc()).all()
    by_module = {}
    rows = db.query(CostLog.module, func.sum(CostLog.amount)).filter(
        CostLog.project_id == project_id).group_by(CostLog.module).all()
    for mod, amt in rows:
        by_module[mod] = round(float(amt), 4)
    spent = cost_model.project_spent(db, project_id)
    percent = round(spent / p.budget_limit * 100, 2) if p.budget_limit else 0.0
    return CostSummaryOut(
        project_id=project_id, total=round(spent, 4), budget_limit=p.budget_limit or 0.0,
        usage_percent=percent, warn_80=80 <= percent < 100, blocked_100=percent >= 100,
        by_module=by_module, logs=[CostLogOut.model_validate(l) for l in logs])


@router.get("/bills", summary="用户账单（按项目汇总）")
def bills(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(CostLog.project_id, func.sum(CostLog.amount), func.count(CostLog.id)).filter(
        CostLog.user_id == user.id).group_by(CostLog.project_id).all()
    items = []
    for pid, amt, cnt in rows:
        p = db.get(Project, pid)
        items.append({"project_id": pid, "project_name": p.name if p else "（已删除）",
                      "total": round(float(amt), 4), "calls": cnt,
                      "created_at": p.created_at.isoformat() if p else ""})
    total = sum(i["total"] for i in items)
    return {"user_id": user.id, "plan": user.plan, "total": round(total, 4), "items": items}


@router.put("/users/me/budget", summary="设置个人预算上限")
def set_budget(budget_limit: float, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    user.budget_limit = max(0.0, budget_limit)
    db.commit()
    return {"budget_limit": user.budget_limit}
