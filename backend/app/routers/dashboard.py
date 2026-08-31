from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..auth import require_roles
from ..database import get_db
from ..models import Client, Installment, InstallmentStatus, Loan, LoanStatus, Payment, User, UserRole
from ..schemas import DashboardOut, DelinquencyClientOut, TopClientOut, UpcomingInstallmentOut
from ..services.analytics import installment_was_late, profit_split

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

UPCOMING_WINDOW_DAYS = 15
TOP_CLIENTS_LIMIT = 10
DELINQUENCY_LIMIT = 5
MIN_INSTALLMENTS_FOR_BEST_PAYER = 1


@router.get("", response_model=DashboardOut)
def get_dashboard(
    company_id: int | None = Query(default=None),
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor)),
    db: Session = Depends(get_db),
):
    scope_company_id = user.company_id if user.role == UserRole.gestor else company_id

    loan_query = db.query(Loan)
    if scope_company_id is not None:
        loan_query = loan_query.filter(Loan.company_id == scope_company_id)

    open_loans = loan_query.filter(Loan.status != LoanStatus.quitado).all()
    total_outstanding_balance = sum((Decimal(str(l.principal)) for l in open_loans), Decimal("0"))

    open_loan_ids = [l.id for l in open_loans]
    total_to_receive = Decimal("0")
    if open_loan_ids:
        rows = (
            db.query(Installment)
            .filter(Installment.loan_id.in_(open_loan_ids), Installment.status != InstallmentStatus.pago)
            .all()
        )
        for inst in rows:
            remaining = Decimal(str(inst.base_amount)) - Decimal(str(inst.paid_amount)) + Decimal(str(inst.late_fee_accrued))
            total_to_receive += max(Decimal("0"), remaining)

    active_loans = sum(1 for l in open_loans if l.status == LoanStatus.ativo)
    overdue_loans = sum(1 for l in open_loans if l.status == LoanStatus.atrasado)
    settled_loans = loan_query.filter(Loan.status == LoanStatus.quitado).count()

    today = date.today()
    horizon = today + timedelta(days=UPCOMING_WINDOW_DAYS)
    upcoming_query = (
        db.query(Installment)
        .join(Loan)
        .options(joinedload(Installment.loan).joinedload(Loan.client))
        .filter(
            Installment.status != InstallmentStatus.pago,
            Installment.due_date >= today,
            Installment.due_date <= horizon,
        )
    )
    if scope_company_id is not None:
        upcoming_query = upcoming_query.filter(Loan.company_id == scope_company_id)
    upcoming = (
        upcoming_query.order_by(Installment.due_date.asc()).limit(50).all()
    )
    upcoming_out = [
        UpcomingInstallmentOut(
            installment_id=i.id,
            loan_id=i.loan_id,
            loan_number=i.loan.loan_number,
            client_id=i.loan.client.id,
            client_name=i.loan.client.name,
            client_phone=i.loan.client.phone,
            due_date=i.due_date,
            amount=float(Decimal(str(i.base_amount)) + Decimal(str(i.late_fee_accrued)) - Decimal(str(i.paid_amount))),
        )
        for i in upcoming
    ]

    top_query = (
        db.query(
            Client.id, Client.name, func.sum(Loan.principal), func.count(Loan.id)
        )
        .join(Loan, Loan.client_id == Client.id)
    )
    if scope_company_id is not None:
        top_query = top_query.filter(Client.company_id == scope_company_id)
    top_rows = (
        top_query.group_by(Client.id, Client.name)
        .order_by(func.sum(Loan.principal).desc())
        .limit(TOP_CLIENTS_LIMIT)
        .all()
    )
    top_clients = [
        TopClientOut(client_id=r[0], client_name=r[1], total_borrowed=float(r[2]), loan_count=r[3])
        for r in top_rows
    ]

    # ---------- Atraso por cliente (quem mais / menos atrasa) ----------
    installments_query = (
        db.query(Installment)
        .join(Loan)
        .join(Client, Client.id == Loan.client_id)
        .options(joinedload(Installment.loan).joinedload(Loan.client))
    )
    if scope_company_id is not None:
        installments_query = installments_query.filter(Loan.company_id == scope_company_id)
    all_installments = installments_query.all()

    per_client: dict[int, dict] = {}
    for inst in all_installments:
        client = inst.loan.client
        entry = per_client.setdefault(
            client.id, {"name": client.name, "total": 0, "late": 0, "late_fee_paid": Decimal("0")}
        )
        entry["total"] += 1
        if installment_was_late(inst):
            entry["late"] += 1
            if inst.status == InstallmentStatus.pago:
                entry["late_fee_paid"] += Decimal(str(inst.late_fee_accrued))

    delinquency_rows = [
        DelinquencyClientOut(
            client_id=client_id,
            client_name=data["name"],
            total_installments=data["total"],
            late_installments=data["late"],
            late_fee_paid=float(data["late_fee_paid"]),
        )
        for client_id, data in per_client.items()
    ]
    most_delinquent = sorted(
        (d for d in delinquency_rows if d.late_installments > 0),
        key=lambda d: (d.late_installments, d.late_fee_paid),
        reverse=True,
    )[:DELINQUENCY_LIMIT]
    best_payers = sorted(
        (d for d in delinquency_rows if d.total_installments >= MIN_INSTALLMENTS_FOR_BEST_PAYER),
        key=lambda d: (d.late_installments, -d.total_installments),
    )[:DELINQUENCY_LIMIT]

    # ---------- Lucro (juros vs. multa por atraso), regime de caixa ----------
    payments_query = db.query(Payment).join(Loan).options(joinedload(Payment.loan))
    if scope_company_id is not None:
        payments_query = payments_query.filter(Loan.company_id == scope_company_id)
    all_payments = payments_query.all()

    interest_profit_total = Decimal("0")
    late_fee_profit_total = Decimal("0")
    month_start = today.replace(day=1)
    monthly_interest_profit = Decimal("0")
    monthly_late_fee_profit = Decimal("0")
    for payment in all_payments:
        interest_profit, late_fee_profit = profit_split(payment, payment.loan)
        interest_profit_total += interest_profit
        late_fee_profit_total += late_fee_profit
        if payment.payment_date >= month_start:
            monthly_interest_profit += interest_profit
            monthly_late_fee_profit += late_fee_profit

    return DashboardOut(
        total_outstanding_balance=float(total_outstanding_balance),
        total_to_receive=float(total_to_receive),
        active_loans=active_loans,
        overdue_loans=overdue_loans,
        settled_loans=settled_loans,
        upcoming_installments=upcoming_out,
        top_clients=top_clients,
        most_delinquent_clients=most_delinquent,
        best_payers=best_payers,
        interest_profit_total=float(interest_profit_total),
        late_fee_profit_total=float(late_fee_profit_total),
        monthly_profit=float(monthly_interest_profit + monthly_late_fee_profit),
        monthly_interest_profit=float(monthly_interest_profit),
        monthly_late_fee_profit=float(monthly_late_fee_profit),
    )
