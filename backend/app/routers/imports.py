import logging
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session

from ..auth import require_consultant_permission, require_roles
from ..config import settings as app_settings
from ..database import get_db
from ..models import Client, Company, Loan, User, UserRole
from ..schemas import MAX_INTEREST_RATE, MAX_LATE_FEE_PER_DAY, MAX_PRINCIPAL
from ..services.cpf_validator import validate_cpf as _validate_cpf
from ..services.audit_logger import log_action
from ..services.interest_engine import calculate_total_amount, generate_installments, next_loan_number
from ..services.telegram import esc, notify_company

router = APIRouter(prefix="/api/imports", tags=["imports"])
logger = logging.getLogger("jurispro.imports")

HEADER_FONT = Font(bold=True)

# Limites do arquivo enviado. Um .xlsx é um ZIP: um arquivo de poucos KB pode
# descompactar para gigabytes ("zip bomb") e derrubar o servidor.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UNZIPPED_BYTES = 50 * 1024 * 1024
MAX_ZIP_ENTRIES = 200
MAX_TERM_MONTHS = 120  # mesmo teto do formulário de novo empréstimo (schemas.LoanCreate)
MAX_SHEET_COLUMNS = 60
MAX_SCAN_ROWS = 50_000  # linhas brutas (inclusive em branco) que aceitamos varrer

COL_NAME = "Nome do Cliente"
COL_DOCUMENT = "CPF do Solicitante"
COL_PHONE = "Telefone"
COL_EMAIL = "Email"
COL_CEP = "CEP"
COL_ADDRESS = "Endereço"
COL_ADDRESS_NUMBER = "Número"
COL_REF1_NAME = "Referência 1 - Nome"
COL_REF1_PHONE = "Referência 1 - Telefone"
COL_REF2_NAME = "Referência 2 - Nome"
COL_REF2_PHONE = "Referência 2 - Telefone"
COL_REF3_NAME = "Referência 3 - Nome"
COL_REF3_PHONE = "Referência 3 - Telefone"
COL_PRINCIPAL = "Valor Solicitado"
COL_RATE = "Taxa de Juros %"
COL_TERM = "Prazo (meses)"
COL_LATE_FEE = "Multa por Atraso R$/dia"
COL_START_DATE = "Data do Empréstimo (AAAA-MM-DD)"
COL_NOTES = "Observações"

TEMPLATE_HEADERS = [
    COL_NAME, COL_DOCUMENT, COL_PHONE, COL_EMAIL, COL_CEP, COL_ADDRESS, COL_ADDRESS_NUMBER,
    COL_REF1_NAME, COL_REF1_PHONE, COL_REF2_NAME, COL_REF2_PHONE, COL_REF3_NAME, COL_REF3_PHONE,
    COL_PRINCIPAL, COL_RATE, COL_TERM, COL_LATE_FEE, COL_START_DATE, COL_NOTES,
]
REQUIRED_HEADERS = [COL_NAME, COL_DOCUMENT]
LOAN_HEADERS = [COL_PRINCIPAL, COL_RATE, COL_TERM, COL_LATE_FEE]


@router.get("/clients-loans/template.xlsx")
def download_template(
    user: User = Depends(require_roles(UserRole.gestor, UserRole.consultor)),
):
    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes e Empréstimos"
    ws.append(TEMPLATE_HEADERS)
    for cell in ws[1]:
        cell.font = HEADER_FONT
    ws.append([
        "Maria Silva", "123.456.789-09", "(11) 99999-0000", "maria@exemplo.com",
        "01310-100", "Avenida Paulista", "1000",
        "José (irmão)", "(11) 98888-0001", "Ana (vizinha)", "(11) 98888-0002", "", "",
        1000, 30, 10, 10, "2026-01-01", "Cliente de exemplo",
    ])
    for column_cells in ws.columns:
        length = max(len(str(c.value)) if c.value is not None else 0 for c in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(max(length + 2, 12), 40)

    instructions = wb.create_sheet("Instruções")
    instructions.append(["Como preencher esta planilha"])
    instructions["A1"].font = Font(bold=True, size=13)
    lines = [
        "",
        "Uma linha = um cliente (+ opcionalmente um empréstimo lançado para ele).",
        "Colunas obrigatórias para o cliente: " + f"{COL_NAME}, {COL_DOCUMENT}" + ".",
        "Para lançar um empréstimo junto, preencha TODAS as colunas de empréstimo (" +
        f"{COL_PRINCIPAL}, {COL_RATE}, {COL_TERM}, {COL_LATE_FEE}" +
        "). Para importar só o cliente (sem empréstimo), deixe essas 4 colunas em branco.",
        "Se o nome do cliente já existir cadastrado na sua empresa, o cliente é reaproveitado",
        "(não duplica) e só um novo empréstimo é lançado para ele — nesse caso o CPF da linha é ignorado.",
        "CPF deve ter 11 dígitos (com ou sem pontuação). As 3 referências são opcionais.",
        "Endereço e Número são opcionais. No site, o Endereço é preenchido automaticamente a partir do",
        "CEP — na planilha, preencha os dois manualmente (Endereço = rua/bairro/cidade, Número = do imóvel).",
        "Taxa de Juros % é o total do período (ex: 30 = 30% sobre o valor solicitado no prazo todo).",
        "Data do Empréstimo no formato AAAA-MM-DD (ex: 2026-01-31). Se deixar em branco, usa a data de hoje.",
        "Não apague a linha de cabeçalho (linha 1).",
    ]
    for line in lines:
        instructions.append([line])

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="jurispro_modelo_importacao.xlsx"'},
    )


def _clean(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _text(value, max_len: int, label: str, row_number: int):
    """Texto de uma célula, limitado ao tamanho da coluna do banco (senão o banco
    recusa a linha com um erro técnico). Número vira texto (telefone digitado sem
    aspas no Excel chega como 21980155573.0)."""
    value = _clean(value)
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    value = str(value)
    if len(value) > max_len:
        raise ValueError(f"Linha {row_number}: '{label}' passa de {max_len} caracteres")
    return value


def _read_xlsx_upload(file: UploadFile) -> bytes:
    """Lê o upload com todas as checagens antes de entregá-lo ao openpyxl."""
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=422, detail="Envie um arquivo .xlsx")
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Arquivo maior que {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    # A extensão é só o nome que o usuário deu: confere se é mesmo um ZIP (assinatura "PK").
    if not content.startswith(b"PK\x03\x04"):
        raise HTTPException(status_code=422, detail="O arquivo não é uma planilha .xlsx válida")
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_ENTRIES or sum(e.file_size for e in entries) > MAX_UNZIPPED_BYTES:
                raise HTTPException(status_code=422, detail="Planilha grande ou complexa demais para importar")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="O arquivo não é uma planilha .xlsx válida")
    return content


def _parse_decimal(value, field_name: str, row_number: int) -> Decimal:
    if value is None or value == "":
        raise ValueError(f"Linha {row_number}: '{field_name}' é obrigatório")
    try:
        number = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Linha {row_number}: '{field_name}' inválido ({value!r})")
    if not number.is_finite():  # "NaN" e "Infinity" são aceitos pelo Decimal
        raise ValueError(f"Linha {row_number}: '{field_name}' inválido ({value!r})")
    return number


def _parse_int(value, field_name: str, row_number: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"Linha {row_number}: '{field_name}' inválido ({value!r})")


def _parse_start_date(value, row_number: int) -> date:
    if value in (None, ""):
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise ValueError(f"Linha {row_number}: 'Data do Empréstimo' inválida ({value!r}), use AAAA-MM-DD")


# `def` (e não `async def`): o trabalho é todo bloqueante (banco de dados). Como
# `async def`, uma planilha grande travava o servidor inteiro enquanto processava;
# como `def`, o FastAPI roda em thread própria e os demais usuários seguem normais.
@router.post("/clients-loans")
def import_clients_loans(
    file: UploadFile = File(...),
    user: User = Depends(require_roles(UserRole.gestor, UserRole.consultor)),
    db: Session = Depends(get_db),
):
    require_consultant_permission(db, user, "register_clients")
    require_consultant_permission(db, user, "register_loans")
    content = _read_xlsx_upload(file)

    max_rows = app_settings.import_max_rows
    too_many = HTTPException(
        status_code=422,
        detail=f"A planilha tem mais de {max_rows} linhas de dados. Divida em arquivos menores.",
    )
    sheet_rows: list[tuple[int, tuple]] = []  # (nº da linha na planilha, valores) — só linhas com dado
    try:
        wb = load_workbook(filename=BytesIO(content), read_only=True, data_only=True)
        try:
            # Leitura em fluxo (nunca a planilha inteira na memória) e com teto de colunas e de
            # linhas: o tamanho que o arquivo declara pode ser gigante. Linhas em branco não
            # contam para o limite, mas o limite é conferido AQUI, antes de gravar qualquer coisa.
            header_values = None
            raw_rows = wb.worksheets[0].iter_rows(
                min_row=1, max_row=MAX_SCAN_ROWS + 1, max_col=MAX_SHEET_COLUMNS, values_only=True
            )
            for row_number, values in enumerate(raw_rows, start=1):
                if row_number == 1:
                    header_values = values
                    continue
                if all(v in (None, "") for v in values):
                    continue
                if row_number > MAX_SCAN_ROWS or len(sheet_rows) >= max_rows:
                    raise too_many
                sheet_rows.append((row_number, values))
        finally:
            wb.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="Não foi possível ler o arquivo. Verifique se é um .xlsx válido")
    if header_values is None:
        raise HTTPException(status_code=422, detail="A planilha está vazia")

    header_row = [str(v).strip() if v is not None else "" for v in header_values]
    header_index = {name: idx for idx, name in enumerate(header_row)}
    missing = [h for h in REQUIRED_HEADERS if h not in header_index]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Cabeçalho da planilha inválido. Colunas faltando: {', '.join(missing)}. Baixe o modelo atualizado.",
        )

    def cell(row, header_name):
        idx = header_index.get(header_name)
        return row[idx] if idx is not None and idx < len(row) else None

    errors: list[dict] = []
    clients_created = 0
    loans_created = 0
    next_number = next_loan_number(db, user.company_id)

    company = db.get(Company, user.company_id)
    max_clients = company.max_clients if company else None
    client_count = db.query(Client).filter(Client.company_id == user.company_id).count()

    existing_clients = {
        c.name.strip().lower(): c
        for c in db.query(Client).filter(Client.company_id == user.company_id).all()
    }

    for row_number, row in sheet_rows:
        savepoint = db.begin_nested()
        try:
            name = _text(cell(row, COL_NAME), 150, COL_NAME, row_number)
            if not name:
                raise ValueError(f"Linha {row_number}: '{COL_NAME}' é obrigatório")

            loan_values = {h: cell(row, h) for h in LOAN_HEADERS}
            loan_filled = [h for h, v in loan_values.items() if v not in (None, "")]
            wants_loan = len(loan_filled) > 0
            if wants_loan and len(loan_filled) < len(LOAN_HEADERS):
                missing = [h for h in LOAN_HEADERS if h not in loan_filled]
                raise ValueError(
                    f"Linha {row_number}: preencha todas as colunas de empréstimo ({', '.join(missing)}) "
                    "ou deixe as 4 em branco para importar só o cliente"
                )

            if wants_loan:
                principal = _parse_decimal(loan_values[COL_PRINCIPAL], COL_PRINCIPAL, row_number)
                rate = _parse_decimal(loan_values[COL_RATE], COL_RATE, row_number)
                term_months = _parse_int(loan_values[COL_TERM], COL_TERM, row_number)
                late_fee = _parse_decimal(loan_values[COL_LATE_FEE], COL_LATE_FEE, row_number)
                start_date = _parse_start_date(cell(row, COL_START_DATE), row_number)
                if principal <= 0:
                    raise ValueError(f"Linha {row_number}: '{COL_PRINCIPAL}' deve ser maior que zero")
                if term_months <= 0:
                    raise ValueError(f"Linha {row_number}: '{COL_TERM}' deve ser maior que zero")
                if rate < 0:
                    raise ValueError(f"Linha {row_number}: '{COL_RATE}' não pode ser negativa")
                if late_fee < 0:
                    raise ValueError(f"Linha {row_number}: '{COL_LATE_FEE}' não pode ser negativa")
                # Tetos: sem eles, um prazo de 50 milhões de meses criava 50 milhões de
                # parcelas, e valores acima da coluna do banco davam erro técnico.
                if term_months > MAX_TERM_MONTHS:
                    raise ValueError(f"Linha {row_number}: '{COL_TERM}' não pode passar de {MAX_TERM_MONTHS} meses")
                if principal > MAX_PRINCIPAL:
                    raise ValueError(f"Linha {row_number}: '{COL_PRINCIPAL}' acima do máximo permitido")
                if rate > MAX_INTEREST_RATE:
                    raise ValueError(f"Linha {row_number}: '{COL_RATE}' acima do máximo permitido ({MAX_INTEREST_RATE}%)")
                if late_fee > MAX_LATE_FEE_PER_DAY:
                    raise ValueError(f"Linha {row_number}: '{COL_LATE_FEE}' acima do máximo permitido")

            client = existing_clients.get(name.lower())
            if client is None:
                if max_clients is not None and client_count >= max_clients:
                    raise ValueError(
                        f"Linha {row_number}: limite de {max_clients} clientes da empresa atingido — "
                        "cliente não importado"
                    )
                raw_document = _clean(cell(row, COL_DOCUMENT))
                if not raw_document:
                    raise ValueError(f"Linha {row_number}: '{COL_DOCUMENT}' é obrigatório para cliente novo")
                try:
                    document = _validate_cpf(raw_document)
                except ValueError as exc:
                    raise ValueError(f"Linha {row_number}: '{COL_DOCUMENT}' {exc} ({raw_document!r})")
                client = Client(
                    company_id=user.company_id,
                    name=name,
                    document=document,
                    phone=_text(cell(row, COL_PHONE), 30, COL_PHONE, row_number),
                    email=_text(cell(row, COL_EMAIL), 150, COL_EMAIL, row_number),
                    cep=_text(cell(row, COL_CEP), 10, COL_CEP, row_number),
                    address=_text(cell(row, COL_ADDRESS), 255, COL_ADDRESS, row_number),
                    address_number=_text(cell(row, COL_ADDRESS_NUMBER), 20, COL_ADDRESS_NUMBER, row_number),
                    notes=_text(cell(row, COL_NOTES), 5000, COL_NOTES, row_number),
                    reference1_name=_text(cell(row, COL_REF1_NAME), 150, COL_REF1_NAME, row_number),
                    reference1_phone=_text(cell(row, COL_REF1_PHONE), 30, COL_REF1_PHONE, row_number),
                    reference2_name=_text(cell(row, COL_REF2_NAME), 150, COL_REF2_NAME, row_number),
                    reference2_phone=_text(cell(row, COL_REF2_PHONE), 30, COL_REF2_PHONE, row_number),
                    reference3_name=_text(cell(row, COL_REF3_NAME), 150, COL_REF3_NAME, row_number),
                    reference3_phone=_text(cell(row, COL_REF3_PHONE), 30, COL_REF3_PHONE, row_number),
                    created_by=user.id,
                )
                db.add(client)
                db.flush()
                existing_clients[name.lower()] = client
                client_count += 1
                clients_created += 1

            if wants_loan:
                total_amount = calculate_total_amount(principal, rate)
                loan = Loan(
                    company_id=user.company_id,
                    loan_number=next_number,
                    client_id=client.id,
                    principal=principal,
                    interest_rate=rate,
                    term_months=term_months,
                    start_date=start_date,
                    late_fee_per_day=late_fee,
                    total_amount=total_amount,
                    created_by=user.id,
                )
                db.add(loan)
                db.flush()
                for installment in generate_installments(loan):
                    installment.loan_id = loan.id
                    db.add(installment)
                loans_created += 1
                next_number += 1
            savepoint.commit()
        except ValueError as exc:
            savepoint.rollback()
            errors.append({"row": row_number, "message": str(exc)})
        except Exception:  # noqa: BLE001 - report and keep processing remaining rows
            savepoint.rollback()
            # O detalhe (SQL, parâmetros, nomes de tabela) fica só no log do servidor.
            logger.exception("Falha inesperada ao importar a linha %s", row_number)
            errors.append({"row": row_number, "message": f"Linha {row_number}: erro inesperado ao processar esta linha"})

    log_action(
        db, user, "importar_planilha", "import_batch", None,
        {"clientes_criados": clients_created, "emprestimos_criados": loans_created, "linhas_com_erro": len(errors)},
        company_id=user.company_id,
    )
    db.commit()

    if loans_created > 0:
        notify_company(
            db, user.company_id,
            (
                f"📥 <b>Importação em massa</b>\n"
                f"{clients_created} cliente(s) e {loans_created} empréstimo(s) importados por {esc(user.name)}"
                + (f"\n⚠️ {len(errors)} linha(s) com erro" if errors else "")
            ),
        )

    return {"clients_created": clients_created, "loans_created": loans_created, "errors": errors}
