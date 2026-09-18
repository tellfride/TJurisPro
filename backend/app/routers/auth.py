from datetime import datetime, timedelta
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..auth import (
    LOCKOUT_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    create_access_token,
    get_client_ip,
    get_current_user,
    get_or_create_ip_attempt,
    new_session_token,
    register_ip_failure,
    register_ip_success,
    verify_password,
)
from ..database import get_db
from ..models import Company, User, UserRole
from ..schemas import LoginRequest, TokenResponse, UserOut
from ..services.consultant_permissions import permissions_dict

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _license_error(company: Company) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"A licença da empresa {company.name} expirou. "
            "Entre em contato com o administrador do sistema para renovar o plano."
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    ip_attempt = get_or_create_ip_attempt(db, get_client_ip(request))

    if ip_attempt.locked_until and ip_attempt.locked_until > now:
        remaining = max(1, ceil((ip_attempt.locked_until - now).total_seconds() / 60))
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=(
                f"Muitas tentativas de login a partir deste endereço. "
                f"Tente novamente em {remaining} minuto(s)."
            ),
        )

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        register_ip_failure(ip_attempt)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email não encontrado")
    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário desativado. Fale com o administrador ou gestor da sua empresa.",
        )

    if user.locked_until and user.locked_until > now:
        remaining = max(1, ceil((user.locked_until - now).total_seconds() / 60))
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Muitas tentativas incorretas. Tente novamente em {remaining} minuto(s).",
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1
        register_ip_failure(ip_attempt)
        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_attempts = 0
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=(
                    f"Senha incorreta. Sua conta foi bloqueada por {LOCKOUT_MINUTES} minutos "
                    f"após {MAX_LOGIN_ATTEMPTS} tentativas erradas."
                ),
            )
        db.commit()
        remaining_tries = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Senha incorreta. Mais {remaining_tries} tentativa(s) antes do bloqueio temporário.",
        )

    if user.role != UserRole.administrador and user.company_id is not None:
        company = db.get(Company, user.company_id)
        if company and company.license_expires_at and company.license_expires_at < now:
            raise _license_error(company)

    register_ip_success(ip_attempt)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.session_token = new_session_token()
    db.commit()
    db.refresh(user)

    token = create_access_token(user)
    user_out = UserOut.model_validate(user)
    if user.role == UserRole.consultor:
        user_out.permissions = permissions_dict(db, user)
    return TokenResponse(access_token=token, user=user_out)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_out = UserOut.model_validate(user)
    if user.role == UserRole.consultor:
        user_out.permissions = permissions_dict(db, user)
    return user_out
