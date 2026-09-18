"""Migração manual: descontinua o papel Operador — o papel Consultor (com
permissões configuráveis) passa a cobrir tudo que o Operador fazia, e mais.

Converte cada usuário com role='operador' para role='consultor', criando
para ele um registro de permissões equivalente ao que o Operador tinha
(cadastra cliente/empréstimo, registra pagamento, manda WhatsApp — sem
Dashboard/Relatórios/Auditoria/editar taxa/quitar). Idempotente: rodar de
novo não faz nada se não sobrar mais nenhum usuário 'operador'.

Uso:
    cd backend
    python migrate_v5.py
"""

from app.database import SessionLocal
from app.models import ConsultantPermissions, User, UserRole

OPERADOR_EQUIVALENT_PERMISSIONS = {
    "view_dashboard": False,
    "register_clients": True,
    "register_loans": True,
    "register_payments": True,
    "edit_rates": False,
    "settle_loans": False,
    "view_reports": False,
    "view_audit": False,
    "send_whatsapp": True,
}


def main() -> None:
    db = SessionLocal()
    try:
        operadores = db.query(User).filter(User.role == UserRole.operador).all()
        if not operadores:
            print("Nenhum usuário com papel Operador encontrado. Nada a fazer.")
            return

        for user in operadores:
            user.role = UserRole.consultor
            perms = db.get(ConsultantPermissions, user.id)
            if not perms:
                perms = ConsultantPermissions(user_id=user.id, **OPERADOR_EQUIVALENT_PERMISSIONS)
                db.add(perms)
            else:
                for field, value in OPERADOR_EQUIVALENT_PERMISSIONS.items():
                    setattr(perms, field, value)
            print(f"Usuário '{user.name}' ({user.email}) migrado de Operador para Consultor")

        db.commit()
        print(f"Migração concluída: {len(operadores)} usuário(s) migrado(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
