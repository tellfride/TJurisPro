from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..auth import assert_company_access, require_roles
from ..database import get_db
from ..models import Company, User, UserRole, WhatsappTemplate
from ..schemas import WhatsappTemplateCreate, WhatsappTemplateOut, WhatsappTemplateUpdate
from ..services.audit_logger import log_action
from ..services.default_whatsapp_templates import ensure_default_templates

router = APIRouter(prefix="/api/whatsapp-templates", tags=["whatsapp-templates"])


def _resolve_company_id(user: User, company_id: int | None) -> int:
    if user.role != UserRole.administrador:
        return user.company_id
    if company_id is None:
        raise HTTPException(status_code=422, detail="Informe company_id")
    return company_id


@router.get("", response_model=list[WhatsappTemplateOut])
def list_templates(
    company_id: int | None = Query(default=None),
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor, UserRole.consultor)),
    db: Session = Depends(get_db),
):
    target_company_id = _resolve_company_id(user, company_id)
    assert_company_access(user, target_company_id)
    return (
        db.query(WhatsappTemplate)
        .filter(WhatsappTemplate.company_id == target_company_id)
        .order_by(WhatsappTemplate.name)
        .all()
    )


@router.post("", response_model=WhatsappTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: WhatsappTemplateCreate,
    company_id: int | None = Query(default=None),
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    target_company_id = _resolve_company_id(user, company_id)
    assert_company_access(user, target_company_id)
    template = WhatsappTemplate(company_id=target_company_id, name=payload.name, content=payload.content)
    db.add(template)
    db.flush()
    log_action(db, user, "criar_modelo_whatsapp", "whatsapp_template", template.id, {"name": template.name}, company_id=target_company_id)
    db.commit()
    db.refresh(template)
    return template


@router.post("/defaults", response_model=list[WhatsappTemplateOut])
def add_default_templates(
    company_id: int | None = Query(default=None),
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    """Adiciona os modelos de cobrança padrão que faltam na empresa (não mexe
    nos que já existem nem nos que o gestor editou). Devolve só os criados."""
    target_company_id = _resolve_company_id(user, company_id)
    assert_company_access(user, target_company_id)
    if not db.get(Company, target_company_id):
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    created = ensure_default_templates(db, target_company_id)
    if created:
        log_action(
            db, user, "criar_modelos_whatsapp_padrao", "whatsapp_template", None,
            {"criados": [t.name for t in created]}, company_id=target_company_id,
        )
    db.commit()
    for template in created:
        db.refresh(template)
    return created


@router.put("/{template_id}", response_model=WhatsappTemplateOut)
def update_template(
    template_id: int,
    payload: WhatsappTemplateUpdate,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    template = db.get(WhatsappTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    assert_company_access(user, template.company_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(template, field, value)
    log_action(db, user, "editar_modelo_whatsapp", "whatsapp_template", template.id, changes, company_id=template.company_id)
    db.commit()
    db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: int,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    template = db.get(WhatsappTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    assert_company_access(user, template.company_id)
    log_action(db, user, "excluir_modelo_whatsapp", "whatsapp_template", template.id, {"name": template.name}, company_id=template.company_id)
    db.delete(template)
    db.commit()
