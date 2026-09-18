"""Migração manual: licenciamento por empresa, papel Consultor, sessão única
e bloqueio de login. Idempotente.

Uso:
    cd backend
    python migrate_v4.py
"""

from sqlalchemy import text

from app.database import engine


def _column_exists(conn, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    ).scalar()
    return bool(row)


def main() -> None:
    with engine.begin() as conn:
        companies_columns = [
            ("license_expires_at", "DATETIME"),
            ("max_clients", "INT"),
        ]
        for column, coltype in companies_columns:
            if not _column_exists(conn, "companies", column):
                conn.execute(text(f"ALTER TABLE companies ADD COLUMN {column} {coltype} NULL"))
                print(f"companies.{column} adicionada")
            else:
                print(f"companies.{column} já existia")

        users_columns = [
            ("failed_login_attempts", "INT NOT NULL DEFAULT 0"),
            ("locked_until", "DATETIME NULL"),
            ("session_token", "VARCHAR(64) NULL"),
        ]
        for column, coldef in users_columns:
            if not _column_exists(conn, "users", column):
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {column} {coldef}"))
                print(f"users.{column} adicionada")
            else:
                print(f"users.{column} já existia")

        # Amplia o ENUM de papéis para incluir 'consultor' — reaplicar o mesmo
        # ENUM é inofensivo caso já tenha sido ampliado antes.
        conn.execute(
            text(
                "ALTER TABLE users MODIFY COLUMN role "
                "ENUM('administrador','gestor','operador','consultor') NOT NULL"
            )
        )
        print("users.role agora aceita 'consultor'")

    # consultant_permissions e whatsapp_templates são tabelas novas — o
    # próprio backend já as cria automaticamente no startup (Base.metadata.create_all).
    print("Migração concluída.")


if __name__ == "__main__":
    main()
