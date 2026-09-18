"""Histórico de uma OS (empréstimo): tudo que aconteceu com ela, em ordem.

Monta a linha do tempo a partir das fontes originais — não de uma cópia — para
nunca ficar defasada nem duplicar evento:
- abertura da OS         -> Loan (created_at / created_by), presente até nos
                            empréstimos criados por importação de planilha
- pagamentos e quitação  -> Payment (a quitação é o Payment sem parcela)
- ajuste de juros/multa  -> AuditLog "editar_emprestimo"
- cobranças por WhatsApp -> AuditLog "cobranca_whatsapp"

Não inclui de propósito "criar_emprestimo", "registrar_pagamento" e
"baixar_emprestimo" do audit log: já aparecem pelas fontes acima.
"""

from sqlalchemy.orm import Session

from ..models import AuditLog, Loan, User

HISTORY_AUDIT_ACTIONS = ("editar_emprestimo", "cobranca_whatsapp")


def _num(value) -> float | None:
    return None if value is None else float(value)


def build_loan_history(db: Session, loan: Loan) -> list[dict]:
    events: list[dict] = []

    events.append({
        "at": loan.created_at,
        "kind": "aberta",
        "user_id": loan.created_by,
        "data": {
            "client": loan.client.name,
            "principal": _num(loan.principal),
            "interest_rate": _num(loan.interest_rate),
            "term_months": loan.term_months,
            "total_amount": _num(loan.total_amount),
            "late_fee_per_day": _num(loan.late_fee_per_day),
        },
    })

    for payment in loan.payments:
        is_payoff = payment.installment_id is None
        events.append({
            "at": payment.created_at,
            "kind": "quitacao" if is_payoff else "pagamento",
            "user_id": payment.registered_by,
            "data": {
                "amount": _num(payment.amount),
                "late_fee_included": _num(payment.late_fee_included),
                "payment_date": payment.payment_date.isoformat(),
                "installment_number": payment.installment.number if payment.installment else None,
                "notes": payment.notes,
            },
        })

    audit_rows = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "loan",
            AuditLog.entity_id == loan.id,
            AuditLog.company_id == loan.company_id,
            AuditLog.action.in_(HISTORY_AUDIT_ACTIONS),
        )
        .all()
    )
    for row in audit_rows:
        events.append({
            "at": row.created_at,
            "kind": "edicao" if row.action == "editar_emprestimo" else "cobranca_whatsapp",
            "user_id": row.user_id,
            "data": row.details or {},
        })

    user_ids = {e["user_id"] for e in events if e["user_id"] is not None}
    names = {}
    if user_ids:
        names = {u.id: u.name for u in db.query(User).filter(User.id.in_(user_ids)).all()}

    events.sort(key=lambda e: e["at"], reverse=True)  # mais recente primeiro
    return [
        {"at": e["at"], "kind": e["kind"], "user_name": names.get(e["user_id"]), "data": e["data"]}
        for e in events
    ]
