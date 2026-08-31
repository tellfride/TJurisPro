"""Cálculo de lucro (juros vs. multa por atraso) e de atraso por cliente,
usados pelo dashboard e pela exportação de transações.

Lucro é apurado em regime de caixa: só conta o que já foi efetivamente pago,
não o que está apenas contratado/em aberto.
"""
from decimal import Decimal

from ..models import Installment, InstallmentStatus, Loan, Payment

ZERO = Decimal("0")


def profit_split(payment: Payment, loan: Loan) -> tuple[Decimal, Decimal]:
    """Divide o valor de um pagamento em (lucro_de_juros, lucro_de_multa).

    A multa (late_fee_included) já é lucro puro. O restante do valor pago é
    rateado proporcionalmente entre recuperação de principal e lucro de juros,
    usando a razão juros/total contratada no empréstimo.
    """
    late_fee_profit = Decimal(str(payment.late_fee_included))
    principal_and_interest = Decimal(str(payment.amount)) - late_fee_profit
    total_amount = Decimal(str(loan.total_amount))
    principal = Decimal(str(loan.principal))
    if total_amount <= 0:
        return ZERO, late_fee_profit
    interest_ratio = max(ZERO, (total_amount - principal)) / total_amount
    interest_profit = principal_and_interest * interest_ratio
    return interest_profit, late_fee_profit


def installment_was_late(installment: Installment) -> bool:
    if installment.status == InstallmentStatus.atrasado:
        return True
    if (
        installment.status == InstallmentStatus.pago
        and installment.paid_date is not None
        and installment.paid_date > installment.due_date
    ):
        return True
    return False
