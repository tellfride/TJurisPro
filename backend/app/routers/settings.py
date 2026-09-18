from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import assert_company_access, require_roles
from ..database import get_db
from ..models import Company, CompanyNotificationSettings, User, UserRole
from ..schemas import SECRET_MASK, NotificationSettingsOut, NotificationSettingsUpdate
from ..services.audit_logger import log_action

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _resolve_company_id(user: User, company_id: int | None) -> int:
    if user.role == UserRole.gestor:
        return user.company_id
    if company_id is None:
        raise HTTPException(status_code=422, detail="Informe company_id")
    return company_id


@router.get("/notifications", response_model=NotificationSettingsOut)
def get_notification_settings(
    company_id: int | None = Query(default=None),
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    target_company_id = _resolve_company_id(user, company_id)
    assert_company_access(user, target_company_id)
    if not db.get(Company, target_company_id):
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    row = db.get(CompanyNotificationSettings, target_company_id)
    if not row:
        row = CompanyNotificationSettings(company_id=target_company_id, notify_days_before=5)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.put("/notifications", response_model=NotificationSettingsOut)
def update_notification_settings(
    payload: NotificationSettingsUpdate,
    company_id: int | None = Query(default=None),
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    target_company_id = _resolve_company_id(user, company_id)
    assert_company_access(user, target_company_id)
    if not db.get(Company, target_company_id):
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    row = db.get(CompanyNotificationSettings, target_company_id)
    if not row:
        row = CompanyNotificationSettings(company_id=target_company_id, notify_days_before=5)
        db.add(row)

    changes = payload.model_dump(exclude_unset=True)
    # A tela recebe o token mascarado (••••1234). Se ele voltar igual, o usuário não
    # mexeu no campo: mantém o token real em vez de gravar a máscara por cima.
    token = changes.get("telegram_bot_token")
    if token and token.startswith(SECRET_MASK):
        del changes["telegram_bot_token"]
    for field, value in changes.items():
        setattr(row, field, value)

    log_action(
        db, user, "editar_configuracao_notificacao", "company_notification_settings",
        target_company_id,
        {k: v for k, v in changes.items() if k != "telegram_bot_token"},
        company_id=target_company_id,
    )
    db.commit()
    db.refresh(row)
    return row
