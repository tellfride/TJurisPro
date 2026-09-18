from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from ..auth import assert_company_access, get_current_user, require_consultant_permission, require_roles
from ..database import get_db
from ..models import Client, Installment, InstallmentStatus, Loan, LoanStatus, Payment, User, UserRole
from ..schemas import (
    LoanCreate,
    LoanDetailOut,
    LoanOut,
    LoanPayoffRequest,
    LoanUpdate,
    PaymentCreate,
    PaymentOut,
)
from ..services.audit_logger import log_action
from ..services.interest_engine import (
    apply_payment,
    calculate_total_amount,
    generate_installments,
    next_loan_number,
    recalculate_open_installments,
    refresh_loan_status,
    suggest_early_payoff,
)
from ..services.telegram import notify_company

router = APIRouter(prefix="/api/loans", tags=["loans"])


def _get_loan_or_404(db: Session, loan_id: int) -> Loan:
    loan = (
        db.query(Loan)
        .options(joinedload(Loan.installments), joinedload(Loan.payments), joinedload(Loan.client))
        .filter(Loan.id == loan_id)
        .first()
    )
    if not loan:
        raise HTTPException(status_code=404, detail="Empréstimo não encontrado")
    return loan


@router.get("", response_model=list[LoanOut])
def list_loans(
    company_id: int | None = Query(default=None),
    client_id: int | None = Query(default=None),
    status_filter: LoanStatus | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Loan)
    if user.role == UserRole.administrador:
        if company_id is not None:
            query = query.filter(Loan.company_id == company_id)
    else:
        query = query.filter(Loan.company_id == user.company_id)
    if client_id is not None:
        query = query.filter(Loan.client_id == client_id)
    if status_filter is not None:
        query = query.filter(Loan.status == status_filter)
    return query.order_by(Loan.created_at.desc()).all()


@router.get("/{loan_id}", response_model=LoanDetailOut)
def get_loan(loan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    loan = _get_loan_or_404(db, loan_id)
    assert_company_access(user, loan.company_id)
    return loan


@router.post("", response_model=LoanDetailOut, status_code=status.HTTP_201_CREATED)
def create_loan(
    payload: LoanCreate,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor, UserRole.consultor)),
    db: Session = Depends(get_db),
):
    if user.role == UserRole.administrador:
        raise HTTPException(status_code=422, detail="Administrador não pertence a uma empresa; use o login de um gestor/consultor para lançar empréstimos")
    require_consultant_permission(db, user, "register_loans")
    client = db.get(Client, payload.client_id)
    if not client or client.company_id != user.company_id:
        raise HTTPException(status_code=404, detail="Cliente não encontrado nesta empresa")

    principal = Decimal(str(payload.principal))
    rate = Decimal(str(payload.interest_rate))
    total = calculate_total_amount(principal, rate)

    loan = Loan(
        company_id=user.company_id,
        loan_number=next_loan_number(db, user.company_id),
        client_id=client.id,
        principal=principal,
        interest_rate=rate,
        term_months=payload.term_months,
        start_date=payload.start_date or date.today(),
        late_fee_per_day=Decimal(str(payload.late_fee_per_day)),
        total_amount=total,
        created_by=user.id,
    )
    db.add(loan)
    db.flush()

    for installment in generate_installments(loan):
        installment.loan_id = loan.id
        db.add(installment)

    log_action(
        db, user, "criar_emprestimo", "loan", loan.id,
        {
            "loan_number": loan.loan_number,
            "client": client.name,
            "principal": float(principal),
            "interest_rate": float(rate),
            "term_months": loan.term_months,
            "total_amount": float(total),
        },
        company_id=user.company_id,
    )
    db.commit()
    db.refresh(loan)

    notify_company(
        db, user.company_id,
        (
            f"💰 <b>Novo empréstimo lançado</b>\n"
            f"Cliente: {client.name}\n"
            f"Valor solicitado: R$ {principal:.2f}\n"
            f"Juros: {rate:.2f}%\n"
            f"Total a pagar: R$ {total:.2f} em {loan.term_months}x\n"
            f"Lançado por: {user.name}"
        ),
    )
    return _get_loan_or_404(db, loan.id)


@router.put("/{loan_id}", response_model=LoanDetailOut)
def update_loan(
    loan_id: int,
    payload: LoanUpdate,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor, UserRole.consultor)),
    db: Session = Depends(get_db),
):
    require_consultant_permission(db, user, "edit_rates")
    loan = _get_loan_or_404(db, loan_id)
    assert_company_access(user, loan.company_id)
    if loan.status == LoanStatus.quitado:
        raise HTTPException(status_code=422, detail="Empréstimo já quitado não pode ser editado")

    changes = payload.model_dump(exclude_unset=True)
    if "interest_rate" in changes:
        loan.interest_rate = Decimal(str(changes["interest_rate"]))
    if "late_fee_per_day" in changes:
        loan.late_fee_per_day = Decimal(str(changes["late_fee_per_day"]))

    recalculate_open_installments(loan)
    refresh_loan_status(loan)

    log_action(db, user, "editar_emprestimo", "loan", loan.id, changes, company_id=loan.company_id)
    db.commit()
    db.refresh(loan)
    return _get_loan_or_404(db, loan.id)


@router.post("/{loan_id}/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def register_payment(
    loan_id: int,
    payload: PaymentCreate,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor, UserRole.consultor)),
    db: Session = Depends(get_db),
):
    require_consultant_permission(db, user, "register_payments")
    loan = _get_loan_or_404(db, loan_id)
    assert_company_access(user, loan.company_id)
    installment = db.get(Installment, payload.installment_id)
    if not installment or installment.loan_id != loan.id:
        raise HTTPException(status_code=404, detail="Parcela não encontrada neste empréstimo")

    if installment.status == InstallmentStatus.pago:
        raise HTTPException(status_code=422, detail="Esta parcela já está paga")

    payment = apply_payment(
        loan, installment, Decimal(str(payload.amount)),
        payload.payment_date or date.today(), user, payload.notes,
    )
    db.add(payment)
    refresh_loan_status(loan)
    log_action(
        db, user, "registrar_pagamento", "installment", installment.id,
        {"amount": payload.amount, "installment_number": installment.number},
        company_id=loan.company_id,
    )
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/{loan_id}/payoff-suggestion")
def payoff_suggestion(
    loan_id: int,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor, UserRole.consultor)),
    db: Session = Depends(get_db),
):
    require_consultant_permission(db, user, "settle_loans")
    loan = _get_loan_or_404(db, loan_id)
    assert_company_access(user, loan.company_id)
    return {"suggested_amount": float(suggest_early_payoff(loan))}


@router.post("/{loan_id}/baixar", response_model=LoanDetailOut)
def settle_loan(
    loan_id: int,
    payload: LoanPayoffRequest,
    user: User = Depends(require_roles(UserRole.administrador, UserRole.gestor, UserRole.consultor)),
    db: Session = Depends(get_db),
):
    require_consultant_permission(db, user, "settle_loans")
    loan = _get_loan_or_404(db, loan_id)
    assert_company_access(user, loan.company_id)
    if loan.status == LoanStatus.quitado:
        raise HTTPException(status_code=422, detail="Empréstimo já está quitado")

    payment_date = payload.payment_date or date.today()
    payoff_amount = Decimal(str(payload.payoff_amount))

    # Credita a multa/juros de atraso já acumulada (e ainda não paga) das
    # parcelas em aberto como lucro de multa, até o limite do valor pago —
    # sem isso, o valor inteiro da quitação seria tratado como juros
    # contratado no dashboard/relatório, mesmo quando o empréstimo estava
    # atrasado e parte do valor é claramente multa.
    open_installments = [i for i in loan.installments if i.status != InstallmentStatus.pago]
    total_late_fee_remaining = sum((i.late_fee_remaining for i in open_installments), Decimal("0"))
    late_fee_included = min(payoff_amount, total_late_fee_remaining)

    payment = Payment(
        loan_id=loan.id,
        installment_id=None,
        amount=payoff_amount,
        late_fee_included=late_fee_included,
        payment_date=payment_date,
        registered_by=user.id,
        notes=payload.notes or "Quitação antecipada",
    )
    db.add(payment)

    for installment in open_installments:
        # Marca a parcela como totalmente paga pelo valor contratado dela —
        # o valor de caixa de fato recebido (possivelmente diferente, se o
        # gestor negociou desconto) fica registrado só uma vez no Payment
        # acima, para não inflar o "pago" de cada parcela individualmente.
        installment.paid_amount = Decimal(str(installment.base_amount)) + Decimal(str(installment.late_fee_accrued))
        installment.status = InstallmentStatus.pago
        installment.paid_date = payment_date

    loan.status = LoanStatus.quitado
    loan.payoff_amount = payoff_amount
    loan.closed_by = user.id
    loan.closed_at = datetime.utcnow()

    log_action(
        db, user, "baixar_emprestimo", "loan", loan.id,
        {"payoff_amount": payload.payoff_amount, "client": loan.client.name},
        company_id=loan.company_id,
    )
    db.commit()
    db.refresh(loan)
    return _get_loan_or_404(db, loan.id)
