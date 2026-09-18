from datetime import date, datetime
from typing import Annotated, Any, Optional

from pydantic import AfterValidator, BaseModel, Field

from .models import InstallmentStatus, LoanStatus, UserRole
from .services.cpf_validator import validate_cpf as _validate_cpf

# E-mail simples (formato, não deliverability): pydantic's EmailStr usa a lib
# email_validator, que rejeita domínios de uso reservado (.local, .test, .example,
# etc.) — comuns em redes internas de empresas — então validamos só o formato.
EmailField = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=150)]


# ---------- Auth ----------
class LoginRequest(BaseModel):
    email: EmailField
    password: str


class UserOut(BaseModel):
    id: int
    company_id: Optional[int]
    name: str
    email: EmailField
    role: UserRole
    active: bool
    permissions: Optional[dict[str, bool]] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Company ----------
class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    license_expires_at: Optional[datetime] = None
    max_clients: Optional[int] = Field(default=None, ge=1)


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    active: Optional[bool] = None
    license_expires_at: Optional[datetime] = None
    max_clients: Optional[int] = Field(default=None, ge=1)


class CompanyOut(BaseModel):
    id: int
    name: str
    active: bool
    license_expires_at: Optional[datetime]
    max_clients: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class LicenseStatusOut(BaseModel):
    license_expires_at: Optional[datetime]
    days_remaining: Optional[int]
    expired: bool


# ---------- User ----------
class UserCreate(BaseModel):
    company_id: Optional[int] = None
    name: str = Field(min_length=2, max_length=150)
    email: EmailField
    password: str = Field(min_length=6)
    role: UserRole


class UserUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)


# ---------- Client ----------
CpfRequired = Annotated[str, AfterValidator(_validate_cpf)]
CpfOptional = Annotated[Optional[str], AfterValidator(lambda v: _validate_cpf(v) if v else v)]


class ClientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    document: CpfRequired = Field(description="CPF do solicitante")
    phone: Optional[str] = None
    email: Optional[str] = None
    cep: Optional[str] = None
    address: Optional[str] = None
    address_number: Optional[str] = None
    notes: Optional[str] = None
    reference1_name: Optional[str] = None
    reference1_phone: Optional[str] = None
    reference2_name: Optional[str] = None
    reference2_phone: Optional[str] = None
    reference3_name: Optional[str] = None
    reference3_phone: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    document: CpfOptional = None
    phone: Optional[str] = None
    email: Optional[str] = None
    cep: Optional[str] = None
    address: Optional[str] = None
    address_number: Optional[str] = None
    notes: Optional[str] = None
    reference1_name: Optional[str] = None
    reference1_phone: Optional[str] = None
    reference2_name: Optional[str] = None
    reference2_phone: Optional[str] = None
    reference3_name: Optional[str] = None
    reference3_phone: Optional[str] = None


class ClientOut(BaseModel):
    id: int
    company_id: int
    name: str
    document: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    cep: Optional[str]
    address: Optional[str]
    address_number: Optional[str]
    notes: Optional[str]
    reference1_name: Optional[str]
    reference1_phone: Optional[str]
    reference2_name: Optional[str]
    reference2_phone: Optional[str]
    reference3_name: Optional[str]
    reference3_phone: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Installment / Payment ----------
class InstallmentOut(BaseModel):
    id: int
    number: int
    due_date: date
    base_amount: float
    late_fee_accrued: float
    late_fee_remaining: float
    paid_amount: float
    paid_date: Optional[date]
    status: InstallmentStatus

    class Config:
        from_attributes = True


class PaymentCreate(BaseModel):
    installment_id: int
    amount: float = Field(gt=0)
    payment_date: Optional[date] = None
    notes: Optional[str] = None


class PaymentOut(BaseModel):
    id: int
    loan_id: int
    installment_id: Optional[int]
    amount: float
    late_fee_included: float
    payment_date: date
    registered_by: Optional[int]
    notes: Optional[str]

    class Config:
        from_attributes = True


# ---------- Loan ----------
class LoanCreate(BaseModel):
    client_id: int
    principal: float = Field(gt=0)
    interest_rate: float = Field(ge=0)
    term_months: int = Field(gt=0, le=120)
    late_fee_per_day: float = Field(ge=0)
    start_date: Optional[date] = None


class LoanUpdate(BaseModel):
    interest_rate: Optional[float] = Field(default=None, ge=0)
    late_fee_per_day: Optional[float] = Field(default=None, ge=0)


class LoanPayoffRequest(BaseModel):
    payoff_amount: float = Field(gt=0)
    payment_date: Optional[date] = None
    notes: Optional[str] = None


class LoanOut(BaseModel):
    id: int
    loan_number: int
    company_id: int
    client_id: int
    principal: float
    interest_rate: float
    term_months: int
    start_date: date
    late_fee_per_day: float
    total_amount: float
    status: LoanStatus
    payoff_amount: Optional[float]
    created_at: datetime
    closed_at: Optional[datetime]

    class Config:
        from_attributes = True


class LoanDetailOut(LoanOut):
    client: ClientOut
    installments: list[InstallmentOut]
    payments: list[PaymentOut]


# ---------- Audit ----------
class AuditLogOut(BaseModel):
    id: int
    company_id: Optional[int]
    user_id: Optional[int]
    action: str
    entity_type: str
    entity_id: Optional[int]
    details: Optional[dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Settings ----------
class NotificationSettingsOut(BaseModel):
    company_id: int
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]
    notify_days_before: int

    class Config:
        from_attributes = True


class NotificationSettingsUpdate(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    notify_days_before: Optional[int] = Field(default=None, ge=0, le=60)


# ---------- Permissões do Consultor ----------
CONSULTANT_PERMISSION_FIELDS = [
    "view_dashboard", "register_clients", "register_loans", "register_payments",
    "edit_rates", "settle_loans", "view_reports", "view_audit", "send_whatsapp",
]


class ConsultantPermissionsOut(BaseModel):
    user_id: int
    view_dashboard: bool
    register_clients: bool
    register_loans: bool
    register_payments: bool
    edit_rates: bool
    settle_loans: bool
    view_reports: bool
    view_audit: bool
    send_whatsapp: bool

    class Config:
        from_attributes = True


class ConsultantPermissionsUpdate(BaseModel):
    view_dashboard: Optional[bool] = None
    register_clients: Optional[bool] = None
    register_loans: Optional[bool] = None
    register_payments: Optional[bool] = None
    edit_rates: Optional[bool] = None
    settle_loans: Optional[bool] = None
    view_reports: Optional[bool] = None
    view_audit: Optional[bool] = None
    send_whatsapp: Optional[bool] = None


# ---------- Modelos de mensagem WhatsApp ----------
class WhatsappTemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    content: str = Field(min_length=1)


class WhatsappTemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    content: Optional[str] = Field(default=None, min_length=1)


class WhatsappTemplateOut(BaseModel):
    id: int
    company_id: int
    name: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Dashboard ----------
class TopClientOut(BaseModel):
    client_id: int
    client_name: str
    total_borrowed: float
    loan_count: int


class UpcomingInstallmentOut(BaseModel):
    installment_id: int
    loan_id: int
    loan_number: int
    client_id: int
    client_name: str
    client_phone: Optional[str]
    due_date: date
    amount: float


class DelinquencyClientOut(BaseModel):
    client_id: int
    client_name: str
    total_installments: int
    late_installments: int
    late_fee_paid: float


class DashboardOut(BaseModel):
    total_outstanding_balance: float
    total_to_receive: float
    active_loans: int
    overdue_loans: int
    settled_loans: int
    upcoming_installments: list[UpcomingInstallmentOut]
    top_clients: list[TopClientOut]
    most_delinquent_clients: list[DelinquencyClientOut]
    best_payers: list[DelinquencyClientOut]
    interest_profit_total: float
    late_fee_profit_total: float
    monthly_profit: float
    monthly_interest_profit: float
    monthly_late_fee_profit: float
