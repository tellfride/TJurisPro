import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import ConsultantPermissions, LoginIpAttempt, User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_MINUTES = 5

# Bloqueio por IP: um robô testando senha em várias contas a partir do
# mesmo endereço não dispara o bloqueio por usuário (cada conta individual
# só vê 1-2 tentativas erradas), então contamos por IP também.
IP_MAX_ATTEMPTS = 3
IP_LOCKOUT_MINUTES = 5


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def new_session_token() -> str:
    return secrets.token_hex(16)


def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_or_create_ip_attempt(db: Session, ip: str) -> LoginIpAttempt:
    record = db.get(LoginIpAttempt, ip)
    if not record:
        record = LoginIpAttempt(ip_address=ip)
        db.add(record)
        db.flush()
    return record


def register_ip_failure(record: LoginIpAttempt) -> None:
    record.failed_attempts += 1
    if record.failed_attempts >= IP_MAX_ATTEMPTS:
        record.locked_until = datetime.utcnow() + timedelta(minutes=IP_LOCKOUT_MINUTES)
        record.failed_attempts = 0


def register_ip_success(record: LoginIpAttempt) -> None:
    record.failed_attempts = 0
    record.locked_until = None


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "company_id": user.company_id,
        "session_token": user.session_token,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub"))
        token_session = payload.get("session_token")
    except (jwt.PyJWTError, TypeError, ValueError):
        raise credentials_error

    user = db.get(User, user_id)
    if user is None or not user.active:
        raise credentials_error
    # Login por sessão única: um novo login gera um session_token novo no
    # banco e invalida qualquer token antigo em circulação (outro
    # dispositivo/aba), mesmo que ele ainda não tenha expirado.
    if not user.session_token or token_session != user.session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sua sessão foi encerrada porque um novo login foi feito em outro dispositivo",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*roles: UserRole):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para acessar este recurso",
            )
        return user

    return dependency


def assert_company_access(user: User, company_id: int) -> None:
    if user.role == UserRole.administrador:
        return
    if user.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem acesso aos dados desta empresa",
        )


def require_consultant_permission(db: Session, user: User, field: str) -> None:
    """Sem efeito para qualquer papel que não seja Consultor. Para um
    Consultor, exige que o gestor tenha habilitado essa permissão específica
    na aba de Particionamento."""
    if user.role != UserRole.consultor:
        return
    perms = db.get(ConsultantPermissions, user.id)
    if not perms or not getattr(perms, field, False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seu gestor não liberou esta permissão para o seu usuário",
        )
