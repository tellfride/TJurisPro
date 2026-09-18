from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..auth import assert_company_access, get_current_user, require_consultant_permission, require_roles
from ..database import get_db
from ..models import Client, Company, User, UserRole
from ..schemas import ClientCreate, ClientOut, ClientUpdate
from ..services.audit_logger import log_action
from ..services.telegram import notify_company

router = APIRouter(prefix="/api/clients", tags=["clients"])


def _scope_query(query, user: User, company_id: int | None):
    if user.role == UserRole.administrador:
        if company_id is not None:
            query = query.filter(Client.company_id == company_id)
    else:
        query = query.filter(Client.company_id == user.company_id)
    return query


@router.get("", response_model=list[ClientOut])
def list_clients(
    company_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = _scope_query(db.query(Client), user, company_id)
    if search:
        query = query.filter(Client.name.ilike(f"%{search}%"))
    return query.order_by(Client.name).all()


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    assert_company_access(user, client.company_id)
    return client


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor, UserRole.consultor)),
    db: Session = Depends(get_db),
):
    if user.role == UserRole.administrador:
        raise HTTPException(status_code=422, detail="Administrador não pertence a uma empresa; use o login de um gestor/consultor para cadastrar clientes")
    require_consultant_permission(db, user, "register_clients")

    company = db.get(Company, user.company_id)
    if company and company.max_clients is not None:
        current_count = db.query(Client).filter(Client.company_id == user.company_id).count()
        if current_count >= company.max_clients:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Limite de {company.max_clients} clientes cadastrados atingido para esta empresa. "
                    "Fale com o administrador do sistema para aumentar o limite do plano."
                ),
            )

    client = Client(company_id=user.company_id, created_by=user.id, **payload.model_dump())
    db.add(client)
    db.flush()
    log_action(db, user, "criar_cliente", "client", client.id, {"name": client.name}, company_id=user.company_id)
    db.commit()
    db.refresh(client)
    notify_company(
        db, user.company_id,
        f"👤 <b>Novo cliente cadastrado</b>\nNome: {client.name}\nCadastrado por: {user.name}",
    )
    return client


@router.put("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    assert_company_access(user, client.company_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(client, field, value)
    log_action(db, user, "editar_cliente", "client", client.id, changes, company_id=client.company_id)
    db.commit()
    db.refresh(client)
    return client
