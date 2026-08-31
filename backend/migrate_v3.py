"""Migração manual: CEP e Número do endereço do cliente. Idempotente.

Uso:
    cd backend
    python migrate_v3.py
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
        columns = [
            ("cep", "VARCHAR(10)"),
            ("address_number", "VARCHAR(20)"),
        ]
        for column, coltype in columns:
            if not _column_exists(conn, "clients", column):
                conn.execute(text(f"ALTER TABLE clients ADD COLUMN {column} {coltype} NULL"))
                print(f"clients.{column} adicionada")
            else:
                print(f"clients.{column} já existia")
    print("Migração concluída.")


if __name__ == "__main__":
    main()
