from sqlalchemy.orm import Session

from ..models import ConsultantPermissions

DEFAULTS = {
    "view_dashboard": False,
    "register_clients": True,
    "register_loans": True,
    "register_payments": True,
    "edit_rates": False,
    "settle_loans": False,
    "view_reports": False,
    "view_audit": False,
    "send_whatsapp": True,
}


def create_default_permissions(db: Session, user_id: int) -> ConsultantPermissions:
    perms = ConsultantPermissions(user_id=user_id, **DEFAULTS)
    db.add(perms)
    db.flush()
    return perms


def permissions_dict(db: Session, user) -> dict[str, bool]:
    perms = db.get(ConsultantPermissions, user.id)
    if not perms:
        return dict(DEFAULTS)
    return {field: getattr(perms, field) for field in DEFAULTS}
