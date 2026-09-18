from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_roles
from ..database import get_db
from ..models import Client, Company, User, UserRole
from ..schemas import CompanyCreate, CompanyOut, CompanyUpdate, LicenseStatusOut
from ..services.audit_logger import log_action

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("", response_model=list[CompanyOut])
def list_companies(
    user: User = Depends(require_roles(UserRole.administrador)),
    db: Session = Depends(get_db),
):
    return db.query(Company).order_by(Company.name).all()


@router.get("/license-status", response_model=LicenseStatusOut)
def get_license_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == UserRole.administrador or user.company_id is None:
        return LicenseStatusOut(license_expires_at=None, days_remaining=None, expired=False)
    company = db.get(Company, user.company_id)
    if not company or not company.license_expires_at:
        return LicenseStatusOut(license_expires_at=None, days_remaining=None, expired=False)
    delta = company.license_expires_at - datetime.utcnow()
    days_remaining = delta.days
    return LicenseStatusOut(
        license_expires_at=company.license_expires_at,
        days_remaining=days_remaining,
        expired=delta.total_seconds() < 0,
    )


@router.get("/{company_id}/client-count")
def get_client_count(
    company_id: int,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    if user.role == UserRole.gestor and user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Sem acesso a esta empresa")
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    count = db.query(Client).filter(Client.company_id == company_id).count()
    return {"count": count, "max_clients": company.max_clients}


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    user: User = Depends(require_roles(UserRole.administrador)),
    db: Session = Depends(get_db),
):
    company = Company(
        name=payload.name,
        license_expires_at=payload.license_expires_at,
        max_clients=payload.max_clients,
    )
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
