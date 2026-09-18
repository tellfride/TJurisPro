import re
from datetime import date, datetime
from typing import Annotated, Any, Optional

from pydantic import AfterValidator, BaseModel, Field, field_validator

from .models import InstallmentStatus, LoanStatus, UserRole
from .services.cpf_validator import validate_cpf as _validate_cpf

# E-mail simples (formato, não deliverability): pydantic's EmailStr usa a lib
# email_validator, que rejeita domínios de uso reservado (.local, .test, .example,
# etc.) — comuns em redes internas de empresas — então validamos só o formato.
EmailField = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=150)]

# Senhas: mínimo 8 (só vale ao CRIAR/TROCAR — quem já tem senha de 6 continua entrando)
# e máximo 128, para o login não aceitar corpo gigante nem gastar CPU à toa.
PASSWORD_MIN = 8
PASSWORD_MAX = 128

# Valores monetários/taxas com teto compatível com as colunas Numeric do banco
# (Numeric(12,2) aceita até 9.999.999.999,99): sem teto, "1e30" ou "Infinity"
# passavam na validação e estouravam no banco como erro 500.
MAX_PRINCIPAL = 100_000_000
MAX_INTEREST_RATE = 1000          # %, Numeric(6,2); total = principal * (1 + taxa/100) <= 1,1 bi
MAX_LATE_FEE_PER_DAY = 100_000    # R$/dia, Numeric(10,2)
MAX_PAYMENT = 1_000_000_000

# Máscara mostrada no lugar do token do bot do Telegram (o valor real nunca sai do servidor).
SECRET_MASK = "•"


def mask_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return SECRET_MASK * 8 + value[-4:]


# ---------- Auth ----------
class LoginRequest(BaseModel):
    email: EmailField
    password: str = Field(max_length=PASSWORD_MAX)


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
    max_clients: Optional[int] = Field(default=None, ge=1, le=1_000_000)


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    active: Optional[bool] = None
    license_expires_at: Optional[datetime] = None
    max_clients: Optional[int] = Field(default=None, ge=1, le=1_000_000)


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
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    role: UserRole


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


# ---------- Client ----------
CpfRequired = Annotated[str, AfterValidator(_validate_cpf)]
CpfOptional = Annotated[Optional[str], AfterValidator(lambda v: _validate_cpf(v) if v else v)]


class ClientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    document: CpfRequired = Field(description="CPF do solicitante")
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=150)
    cep: Optional[str] = Field(default=None, max_length=10)
    address: Optional[str] = Field(default=None, max_length=255)
    address_number: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=5000)
    reference1_name: Optional[str] = Field(default=None, max_length=150)
    reference1_phone: Optional[str] = Field(default=None, max_length=30)
    reference2_name: Optional[str] = Field(default=None, max_length=150)
    reference2_phone: Optional[str] = Field(default=None, max_length=30)
    reference3_name: Optional[str] = Field(default=None, max_length=150)
    reference3_phone: Optional[str] = Field(default=None, max_length=30)


class ClientUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    document: CpfOptional = None
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=150)
    cep: Optional[str] = Field(default=None, max_length=10)
    address: Optional[str] = Field(default=None, max_length=255)
    address_number: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=5000)
    reference1_name: Optional[str] = Field(default=None, max_length=150)
    reference1_phone: Optional[str] = Field(default=None, max_length=30)
    reference2_name: Optional[str] = Field(default=None, max_length=150)
    reference2_phone: Optional[str] = Field(default=None, max_length=30)
    reference3_name: Optional[str] = Field(default=None, max_length=150)
    reference3_phone: Optional[str] = Field(default=None, max_length=30)


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
    amount: float = Field(gt=0, le=MAX_PAYMENT)
    payment_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=255)


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
    principal: float = Field(gt=0, le=MAX_PRINCIPAL)
    interest_rate: float = Field(ge=0, le=MAX_INTEREST_RATE)
    term_months: int = Field(gt=0, le=120)
    late_fee_per_day: float = Field(ge=0, le=MAX_LATE_FEE_PER_DAY)
    start_date: Optional[date] = None


class LoanUpdate(BaseModel):
    interest_rate: Optional[float] = Field(default=None, ge=0, le=MAX_INTEREST_RATE)
    late_fee_per_day: Optional[float] = Field(default=None, ge=0, le=MAX_LATE_FEE_PER_DAY)


class LoanPayoffRequest(BaseModel):
    payoff_amount: float = Field(gt=0, le=MAX_PAYMENT)
    payment_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=255)


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
    # Só preenchido pela listagem (GET /loans): vencimento da próxima parcela em
    # aberto (ou, se todas as abertas já venceram, a mais antiga delas).
    next_due_date: Optional[date] = None

    class Config:
        from_attributes = True


class LoanDetailOut(LoanOut):
    client: ClientOut
    installments: list[InstallmentOut]
    payments: list[PaymentOut]


class LoanHistoryEventOut(BaseModel):
    """Um item do histórico da OS (empréstimo). `kind` diz o tipo e `data` traz
    os campos daquele tipo (ver services/loan_history.py) — o frontend formata."""

    at: datetime
    kind: str
    user_name: Optional[str] = None
    data: dict[str, Any] = {}


class LoanWhatsappChargeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    template: Optional[str] = Field(default=None, max_length=100)


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

    @field_validator("telegram_bot_token")
    @classmethod
    def _mask_token(cls, value: Optional[str]) -> Optional[str]:
        # O token dá controle total do bot: quem o lê pode ler as conversas e enviar
        # mensagens em nome da empresa. A tela só precisa saber SE existe e os
        # últimos caracteres; o valor completo nunca volta do servidor.
        return mask_secret(value)


class NotificationSettingsUpdate(BaseModel):
    # Formato do token do @BotFather: "<id numérico>:<35 caracteres>". Validar evita
    # lixo e impede que o valor vire outro caminho na URL da API do Telegram
    # (o token é colocado em https://api.telegram.org/bot<TOKEN>/sendMessage).
    telegram_bot_token: Optional[str] = Field(default=None, max_length=100)
    # ID numérico do chat/grupo (grupos são negativos) ou @nome_do_canal.
    telegram_chat_id: Optional[str] = Field(default=None, max_length=64)
    notify_days_before: Optional[int] = Field(default=None, ge=0, le=60)

    @field_validator("telegram_bot_token")
    @classmethod
    def _check_token(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value.startswith(SECRET_MASK):
            return value  # None = apagar; valor mascarado = "não alterar" (tratado no router)
        if not re.fullmatch(r"\d{5,15}:[A-Za-z0-9_-]{30,60}", value):
            raise ValueError("Token do bot inválido. Cole o token exatamente como o @BotFather enviou.")
        return value

    @field_validator("telegram_chat_id")
    @classmethod
    def _check_chat_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not re.fullmatch(r"-?\d{1,20}|@[A-Za-z0-9_]{5,32}", value):
            raise ValueError("ID do chat inválido. Use o número do chat/grupo (ex.: -1001234567890) ou @nome_do_canal.")
        return value


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
    content: str = Field(min_length=1, max_length=2000)


class WhatsappTemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    content: Optional[str] = Field(default=None, min_length=1, max_length=2000)


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
