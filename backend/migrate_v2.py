"""Migração manual para os campos novos: referências do cliente e número de
ordem do empréstimo (a criação de tabelas novas continua automática via
Base.metadata.create_all no startup — isso aqui só ajusta tabelas que já
existem em bancos criados antes desta versão). Idempotente: pode rodar mais
de uma vez sem erro.

Uso:
    cd backend
    python migrate_v2.py
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


def _index_exists(conn, table: str, index_name: str) -> bool:
    row = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = :table AND index_name = :index_name"
        ),
        {"table": table, "index_name": index_name},
    ).scalar()
    return bool(row)


def main() -> None:
    with engine.begin() as conn:
        # ---------- clients: contatos de referência ----------
        reference_columns = [
            ("reference1_name", "VARCHAR(150)"),
            ("reference1_phone", "VARCHAR(30)"),
            ("reference2_name", "VARCHAR(150)"),
            ("reference2_phone", "VARCHAR(30)"),
            ("reference3_name", "VARCHAR(150)"),
            ("reference3_phone", "VARCHAR(30)"),
        ]
        for column, coltype in reference_columns:
            if not _column_exists(conn, "clients", column):
                conn.execute(text(f"ALTER TABLE clients ADD COLUMN {column} {coltype} NULL"))
                print(f"clients.{column} adicionada")
            else:
                print(f"clients.{column} já existia")

        # ---------- loans: número de ordem por empresa ----------
        if not _column_exists(conn, "loans", "loan_number"):
            conn.execute(text("ALTER TABLE loans ADD COLUMN loan_number INT NULL"))
            print("loans.loan_number adicionada")

            # backfill: numera sequencialmente os empréstimos já existentes de
            # cada empresa, na ordem em que foram criados
            company_ids = [r[0] for r in conn.execute(text("SELECT id FROM companies")).all()]
            for company_id in company_ids:
                loan_ids = [
                    r[0]
                    for r in conn.execute(
                        text("SELECT id FROM loans WHERE company_id = :cid ORDER BY created_at, id"),
                        {"cid": company_id},
                    ).all()
                ]
                for number, loan_id in enumerate(loan_ids, start=1):
                    conn.execute(
                        text("UPDATE loans SET loan_number = :n WHERE id = :lid"),
                        {"n": number, "lid": loan_id},
                    )
            print(f"loan_number preenchido para empréstimos existentes ({len(company_ids)} empresa(s))")

            conn.execute(text("ALTER TABLE loans MODIFY COLUMN loan_number INT NOT NULL"))
            print("loans.loan_number marcada como NOT NULL")
        else:
            print("loans.loan_number já existia")

        if not _index_exists(conn, "loans", "uq_loan_company_number"):
            conn.execute(
                text("ALTER TABLE loans ADD CONSTRAINT uq_loan_company_number UNIQUE (company_id, loan_number)")
            )
            print("índice único uq_loan_company_number criado")
        else:
            print("índice único uq_loan_company_number já existia")

    print("Migração concluída.")


if __name__ == "__main__":
    main()
