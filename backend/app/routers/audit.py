from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..database import get_db
from ..models import AuditLog, User, UserRole
from ..schemas import AuditLogOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(
    company_id: int | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    current_user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)
    if current_user.role == UserRole.gestor:
        query = query.filter(AuditLog.company_id == current_user.company_id)
    elif company_id is not None:
        query = query.filter(AuditLog.company_id == company_id)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if date_from is not None:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to is not None:
        # created_at é DATETIME; comparar direto com uma DATE trunca pra
        # meia-noite e exclui o resto do próprio dia selecionado — em vez
        # disso, usamos "antes do início do dia seguinte".
        query = query.filter(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
