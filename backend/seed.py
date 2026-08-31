"""Cria as tabelas (se não existirem) e o primeiro usuário Administrador,
usando os dados definidos em backend/.env (ADMIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD).

Uso:
    cd backend
    python seed.py
"""

from app.auth import hash_password
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import User, UserRole


def main() -> None:
    if not settings.admin_password:
        raise SystemExit("Defina ADMIN_PASSWORD no arquivo backend/.env antes de rodar o seed.")

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.admin_email).first()
        if existing:
            print(f"Usuário administrador '{settings.admin_email}' já existe. Nada a fazer.")
            return

        admin = User(
            company_id=None,
            name=settings.admin_name,
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            role=UserRole.administrador,
            active=True,
        )
        db.add(admin)
        db.commit()
        print(f"Administrador criado: {settings.admin_email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
