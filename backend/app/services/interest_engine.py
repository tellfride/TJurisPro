"""Motor de cálculo de juros, parcelas e multa por atraso do JurisPRO.

Regra de negócio (definida com o usuário):
- total a pagar = principal * (1 + taxa_de_juros / 100), dividido em `term_months`
  parcelas mensais iguais (a última absorve a diferença de arredondamento).
- cada dia de atraso de uma parcela soma `late_fee_per_day` (definido pelo gestor)
  ao valor da parcela, recalculado a partir dos dias corridos de atraso (idempotente:
  pode rodar o job diário quantas vezes for preciso, ou até "pular" dias, que o valor
  fica sempre correto porque é recalculado do zero a cada execução).
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Installment, InstallmentStatus, Loan, LoanStatus, Payment, User

TWO_PLACES = Decimal("0.01")


def next_loan_number(db: Session, company_id: int) -> int:
    """Número de ordem sequencial do próximo empréstimo desta empresa (1, 2, 3...).

    Independente do cliente — a mesma pessoa pode ter vários empréstimos, cada
    um com seu próprio número, o que distingue claramente qual é qual."""
    last_number = db.query(func.max(Loan.loan_number)).filter(Loan.company_id == company_id).scalar()
    return (last_number or 0) + 1


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _add_months(base: date, months: int) -> date:
    month_index = base.month - 1 + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(
        base.day,
        [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
         31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1],
    )
    return date(year, month, day)


def calculate_total_amount(principal: Decimal, interest_rate: Decimal) -> Decimal:
    return _money(principal * (Decimal("1") + interest_rate / Decimal("100")))


def generate_installments(loan: Loan) -> list[Installment]:
    """Gera as parcelas mensais de um empréstimo recém-criado."""
    total = Decimal(str(loan.total_amount))
    n = loan.term_months
    base_value = _money(total / n)
    installments: list[Installment] = []
    running_total = Decimal("0")
    for i in range(1, n + 1):
        amount = base_value
        if i == n:
            amount = _money(total - running_total)
        running_total += amount
        installments.append(
            Installment(
                number=i,
                due_date=_add_months(loan.start_date, i),
                base_amount=amount,
                late_fee_accrued=Decimal("0"),
                paid_amount=Decimal("0"),
                status=InstallmentStatus.pendente,
            )
        )
    return installments


def recalculate_open_installments(loan: Loan) -> None:
    """Redistribui o saldo em aberto quando a taxa de juros é editada.

    Parcelas já pagas não são tocadas. O restante do total (descontado o que
    já foi pago em parcelas quitadas) é dividido igualmente entre as parcelas
    ainda abertas, mantendo os vencimentos originais.
    """
    total = calculate_total_amount(Decimal(str(loan.principal)), Decimal(str(loan.interest_rate)))
    loan.total_amount = total

    open_installments = [i for i in loan.installments if i.status != InstallmentStatus.pago]
    if not open_installments:
        return
    paid_total = sum((Decimal(str(i.base_amount)) for i in loan.installments if i.status == InstallmentStatus.pago), Decimal("0"))
    remaining = total - paid_total

    if remaining <= 0:
        # O novo total (menor) já está totalmente coberto pelo que foi pago
        # nas parcelas quitadas — zera as parcelas abertas em vez de deixar
        # o valor antigo (mais alto) parado nelas, e já marca como pagas
        # já que não sobra nada a cobrar.
        for inst in open_installments:
            inst.base_amount = Decimal("0")
            inst.paid_date = inst.paid_date or date.today()
            inst.status = InstallmentStatus.pago
        return

    n = len(open_installments)
    base_value = _money(remaining / n)
    running = Decimal("0")
    for idx, inst in enumerate(open_installments, start=1):
        amount = base_value
        if idx == n:
            amount = _money(remaining - running)
        running += amount
        inst.base_amount = amount


def suggest_early_payoff(loan: Loan) -> Decimal:
    """Sugestão de valor para quitação antecipada: soma do saldo em aberto
    (parcela + multa acumulada - já pago, incluindo pagamentos parciais
    de juros já feitos) de cada parcela ainda não quitada. O gestor pode
    ajustar o valor final."""
    total = Decimal("0")
    for inst in loan.installments:
        if inst.status == InstallmentStatus.pago:
            continue
        base = Decimal(str(inst.base_amount))
        paid = Decimal(str(inst.paid_amount))
        late_fee = Decimal(str(inst.late_fee_accrued))
        remaining = base + late_fee - paid
        total += max(Decimal("0"), remaining)
    return _money(total)


def apply_payment(loan: Loan, installment: Installment, amount: Decimal, payment_date: date, user: User | None, notes: str | None) -> Payment:
    # late_fee_remaining já desconta a multa/juros de atraso cobertos por
    # pagamentos anteriores desta parcela (ex: um "pagar só os juros" seguido
    # de um pagamento posterior do restante) — evita contar a mesma multa
    # como paga duas vezes.
    late_fee_remaining = installment.late_fee_remaining
    payment = Payment(
        loan_id=loan.id,
        installment_id=installment.id,
        amount=_money(amount),
        late_fee_included=min(_money(amount), late_fee_remaining),
        payment_date=payment_date,
        registered_by=user.id if user else None,
        notes=notes,
    )
    installment.paid_amount = _money(Decimal(str(installment.paid_amount)) + amount)
    due = Decimal(str(installment.base_amount)) + Decimal(str(installment.late_fee_accrued))
    if installment.paid_amount >= due:
        installment.status = InstallmentStatus.pago
        installment.paid_date = payment_date
    return payment


def refresh_loan_status(loan: Loan) -> None:
    if loan.status == LoanStatus.quitado:
        return
    statuses = [i.status for i in loan.installments]
    if statuses and all(s == InstallmentStatus.pago for s in statuses):
        loan.status = LoanStatus.quitado
        loan.closed_at = loan.closed_at or datetime.utcnow()
    elif any(s == InstallmentStatus.atrasado for s in statuses):
        loan.status = LoanStatus.atrasado
    else:
        loan.status = LoanStatus.ativo


def recompute_overdue_installments(db: Session) -> int:
    """Job diário: recalcula multa por atraso e status de todas as parcelas
    em aberto. Idempotente — pode rodar mais de uma vez por dia sem duplicar
    a multa, pois o valor é sempre recalculado a partir dos dias de atraso."""
    today = date.today()
    changed = 0
    open_installments = (
        db.query(Installment)
        .filter(Installment.status != InstallmentStatus.pago)
        .all()
    )
    touched_loans: dict[int, Loan] = {}
    for inst in open_installments:
        days_late = (today - inst.due_date).days
        if days_late > 0:
            new_fee = _money(Decimal(days_late) * Decimal(str(inst.loan.late_fee_per_day)))
            if Decimal(str(inst.late_fee_accrued)) != new_fee:
                inst.late_fee_accrued = new_fee
                changed += 1
            if inst.status != InstallmentStatus.atrasado:
                inst.status = InstallmentStatus.atrasado
                changed += 1
        else:
            if inst.status != InstallmentStatus.pendente:
                inst.status = InstallmentStatus.pendente
                changed += 1
        touched_loans[inst.loan_id] = inst.loan

    for loan in touched_loans.values():
        refresh_loan_status(loan)

    return changed
