from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, hash_password, require_roles
from ..database import get_db
from ..models import Company, ConsultantPermissions, User, UserRole
from ..schemas import (
    ConsultantPermissionsOut,
    ConsultantPermissionsUpdate,
    UserCreate,
    UserOut,
    UserUpdate,
)
from ..services.audit_logger import log_action
from ..services.consultant_permissions import create_default_permissions, permissions_dict

router = APIRouter(prefix="/api/users", tags=["users"])

GESTOR_MANAGEABLE_ROLES = (UserRole.consultor,)


def _user_out(user: User, db: Session) -> UserOut:
    out = UserOut.model_validate(user)
    if user.role == UserRole.consultor:
        out.permissions = permissions_dict(db, user)
    return out


@router.get("", response_model=list[UserOut])
def list_users(
    company_id: int | None = Query(default=None),
    role: UserRole | None = Query(default=None),
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if user.role == UserRole.gestor:
        query = query.filter(User.company_id == user.company_id)
    elif company_id is not None:
        query = query.filter(User.company_id == company_id)
    if role is not None:
        query = query.filter(User.role == role)
    rows = query.order_by(User.name).all()
    return [_user_out(row, db) for row in rows]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    if payload.role == UserRole.operador:
        raise HTTPException(status_code=422, detail="O papel Operador foi descontinuado — cadastre como Consultor")

    if user.role == UserRole.gestor:
        if payload.role not in GESTOR_MANAGEABLE_ROLES:
            raise HTTPException(status_code=403, detail="Gestor só pode cadastrar usuários consultores")
        company_id = user.company_id
    else:
        if payload.role != UserRole.administrador and not payload.company_id:
            raise HTTPException(status_code=422, detail="Informe a empresa para este usuário")
        company_id = payload.company_id if payload.role != UserRole.administrador else None
        if company_id is not None and not db.get(Company, company_id):
            raise HTTPException(status_code=404, detail="Empresa não encontrada")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Já existe um usuário com este email")

    new_user = User(
        company_id=company_id,
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(new_user)
    db.flush()
    if new_user.role == UserRole.consultor:
        create_default_permissions(db, new_user.id)
    log_action(
        db, user, "criar_usuario", "user", new_user.id,
        {"name": new_user.name, "email": new_user.email, "role": new_user.role.value},
        company_id=company_id,
    )
    db.commit()
    db.refresh(new_user)
    return _user_out(new_user, db)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user.role == UserRole.gestor and (
        target.company_id != user.company_id or target.role not in GESTOR_MANAGEABLE_ROLES
    ):
        raise HTTPException(status_code=403, detail="Gestor só pode editar consultores da própria empresa")

    changes = payload.model_dump(exclude_unset=True)
    if "password" in changes:
        password = changes.pop("password")
        if password:
            target.password_hash = hash_password(password)
            target.session_token = None  # força novo login em todos os dispositivos
    for field, value in changes.items():
        setattr(target, field, value)

    log_action(db, user, "editar_usuario", "user", target.id, {k: v for k, v in changes.items()}, company_id=target.company_id)
    db.commit()
    db.refresh(target)
    return _user_out(target, db)


@router.get("/{user_id}/permissions", response_model=ConsultantPermissionsOut)
def get_consultant_permissions(
    user_id: int,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target or target.role != UserRole.consultor:
        raise HTTPException(status_code=404, detail="Consultor não encontrado")
    if user.role == UserRole.gestor and target.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="Sem acesso a este usuário")

    perms = db.get(ConsultantPermissions, target.id)
    if not perms:
        perms = create_default_permissions(db, target.id)
        db.commit()
        db.refresh(perms)
    return perms


@router.put("/{user_id}/permissions", response_model=ConsultantPermissionsOut)
def update_consultant_permissions(
    user_id: int,
    payload: ConsultantPermissionsUpdate,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target or target.role != UserRole.consultor:
        raise HTTPException(status_code=404, detail="Consultor não encontrado")
    if user.role == UserRole.gestor and target.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="Sem acesso a este usuário")

    perms = db.get(ConsultantPermissions, target.id)
    if not perms:
        perms = create_default_permissions(db, target.id)

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(perms, field, value)

    log_action(db, user, "editar_permissoes_consultor", "user", target.id, changes, company_id=target.company_id)
    db.commit()
    db.refresh(perms)
    return perms
