from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_roles
from ..database import get_db
from ..models import Company, User, UserRole
from ..schemas import CompanyCreate, CompanyOut, CompanyUpdate
from ..services.audit_logger import log_action

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("", response_model=list[CompanyOut])
def list_companies(
    user: User = Depends(require_roles(UserRole.administrador)),
    db: Session = Depends(get_db),
):
    return db.query(Company).order_by(Company.name).all()


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    user: User = Depends(require_roles(UserRole.administrador)),
    db: Session = Depends(get_db),
):
    company = Company(name=payload.name)
    db.add(company)
    db.flush()
    log_action(db, user, "criar_empresa", "company", company.id, {"name": company.name}, company_id=company.id)
    db.commit()
    db.refresh(company)
    return company


@router.put("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    user: User = Depends(require_roles(UserRole.administrador)),
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(company, field, value)
    log_action(db, user, "editar_empresa", "company", company.id, changes, company_id=company.id)
    db.commit()
    db.refresh(company)
    return company
