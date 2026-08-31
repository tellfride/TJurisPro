import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class UserRole(str, enum.Enum):
    administrador = "administrador"
    gestor = "gestor"
    operador = "operador"


class LoanStatus(str, enum.Enum):
    ativo = "ativo"
    atrasado = "atrasado"
    quitado = "quitado"


class InstallmentStatus(str, enum.Enum):
    pendente = "pendente"
    pago = "pago"
    atrasado = "atrasado"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="company")
    clients: Mapped[list["Client"]] = relationship(back_populates="company")
    notification_settings: Mapped["CompanyNotificationSettings"] = relationship(
        back_populates="company", uselist=False
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    company: Mapped[Company | None] = relationship(back_populates="users")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    document: Mapped[str | None] = mapped_column(String(30), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cep: Mapped[str | None] = mapped_column(String(10), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference1_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    reference1_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference2_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    reference2_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference3_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    reference3_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    company: Mapped[Company] = relationship(back_populates="clients")
    loans: Mapped[list["Loan"]] = relationship(back_populates="client")


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (UniqueConstraint("company_id", "loan_number", name="uq_loan_company_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    loan_number: Mapped[int] = mapped_column(Integer, nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    principal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    interest_rate: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    late_fee_per_day: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[LoanStatus] = mapped_column(Enum(LoanStatus), default=LoanStatus.ativo, nullable=False)
    payoff_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    client: Mapped[Client] = relationship(back_populates="loans")
    company: Mapped[Company] = relationship()
    installments: Mapped[list["Installment"]] = relationship(
        back_populates="loan", order_by="Installment.number", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="loan")


class Installment(Base):
    __tablename__ = "installments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    loan_id: Mapped[int] = mapped_column(ForeignKey("loans.id"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    base_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    late_fee_accrued: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    paid_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    paid_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    status: Mapped[InstallmentStatus] = mapped_column(
        Enum(InstallmentStatus), default=InstallmentStatus.pendente, nullable=False
    )

    loan: Mapped[Loan] = relationship(back_populates="installments")
    payments: Mapped[list["Payment"]] = relationship(back_populates="installment")

    @property
    def late_fee_remaining(self) -> Decimal:
        """Multa/juros de atraso ainda não paga desta parcela (pode ser paga
        isoladamente, sem quitar o restante da parcela — ver 'pagar só os juros')."""
        paid_late_fee = sum(
            (Decimal(str(p.late_fee_included)) for p in self.payments), Decimal("0")
        )
        return max(Decimal("0"), Decimal(str(self.late_fee_accrued)) - paid_late_fee)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    loan_id: Mapped[int] = mapped_column(ForeignKey("loans.id"), nullable=False)
    installment_id: Mapped[int | None] = mapped_column(ForeignKey("installments.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    late_fee_included: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    payment_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    registered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    loan: Mapped[Loan] = relationship(back_populates="payments")
    installment: Mapped[Installment | None] = relationship(back_populates="payments")
    registered_by_user: Mapped[User | None] = relationship(foreign_keys=[registered_by])


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CompanyNotificationSettings(Base):
    __tablename__ = "company_notification_settings"

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    telegram_bot_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notify_days_before: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    company: Mapped[Company] = relationship(back_populates="notification_settings")


class NotificationLog(Base):
    __tablename__ = "notifications_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    installment_id: Mapped[int | None] = mapped_column(ForeignKey("installments.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
