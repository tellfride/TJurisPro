from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import AuditLog, User


def log_action(
    db: Session,
    user: Optional[User],
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
    company_id: Optional[int] = None,
) -> None:
    entry = AuditLog(
        company_id=company_id if company_id is not None else (user.company_id if user else None),
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.add(entry)
