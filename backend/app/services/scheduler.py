import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..database import SessionLocal
from ..models import Company, CompanyNotificationSettings, Installment, InstallmentStatus, NotificationLog
from . import backup as backup_service
from . import telegram as telegram_service
from .interest_engine import recompute_overdue_installments

logger = logging.getLogger("jurispro.scheduler")

DUE_SOON_TYPE = "vencimento_proximo"
DUE_SOON_LIST_DAYS = 3
LICENSE_WARNING_DAYS = 7


def accrual_job() -> None:
    db = SessionLocal()
    try:
        changed = recompute_overdue_installments(db)
        db.commit()
        logger.info("accrual_job: %s parcela(s) atualizada(s)", changed)
    except Exception:
        db.rollback()
        logger.exception("accrual_job falhou")
    finally:
        db.close()


def notify_job() -> None:
    db = SessionLocal()
    try:
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        companies = db.query(Company).filter(Company.active.is_(True)).all()
        for company in companies:
            settings_row = db.get(CompanyNotificationSettings, company.id)
            if not settings_row or not settings_row.telegram_bot_token or not settings_row.telegram_chat_id:
                continue
            horizon = today + timedelta(days=settings_row.notify_days_before)
            due_soon = (
                db.query(Installment)
                .join(Installment.loan)
                .filter(
                    Installment.status != InstallmentStatus.pago,
                    Installment.due_date >= today,
                    Installment.due_date <= horizon,
                )
                .all()
            )
            for inst in due_soon:
                if inst.loan.company_id != company.id:
                    continue
                already_sent = (
                    db.query(NotificationLog)
                    .filter(
                        NotificationLog.installment_id == inst.id,
                        NotificationLog.type == DUE_SOON_TYPE,
                        NotificationLog.sent_at >= today_start,
                    )
                    .first()
                )
                if already_sent:
                    continue
                client_name = inst.loan.client.name
                text = (
                    f"⏰ <b>Vencimento próximo</b>\n"
                    f"Cliente: {telegram_service.esc(client_name)}\n"
                    f"Parcela {inst.number} do empréstimo #{inst.loan_id}\n"
                    f"Valor: R$ {inst.base_amount:.2f}\n"
                    f"Vencimento: {inst.due_date.strftime('%d/%m/%Y')}"
                )
                if telegram_service.send_message(
                    settings_row.telegram_bot_token, settings_row.telegram_chat_id, text
                ):
                    db.add(NotificationLog(company_id=company.id, installment_id=inst.id, type=DUE_SOON_TYPE))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("notify_job falhou")
    finally:
        db.close()


def due_soon_list_job() -> None:
    """Envia, ao meio-dia, uma lista consolidada no Telegram com todas as
    parcelas de cada empresa que vencem nos próximos DUE_SOON_LIST_DAYS dias.
    """
    db = SessionLocal()
    try:
        today = date.today()
        horizon = today + timedelta(days=DUE_SOON_LIST_DAYS)
        companies = db.query(Company).filter(Company.active.is_(True)).all()
        for company in companies:
            settings_row = db.get(CompanyNotificationSettings, company.id)
            if not settings_row or not settings_row.telegram_bot_token or not settings_row.telegram_chat_id:
                continue
            due_soon = (
                db.query(Installment)
                .join(Installment.loan)
                .filter(
                    Installment.status != InstallmentStatus.pago,
                    Installment.due_date >= today,
                    Installment.due_date <= horizon,
                )
                .order_by(Installment.due_date.asc())
                .all()
            )
            due_soon = [inst for inst in due_soon if inst.loan.company_id == company.id]
            if not due_soon:
                continue

            lines = [f"📋 <b>Vencimentos nos próximos {DUE_SOON_LIST_DAYS} dias</b> ({telegram_service.esc(company.name)})"]
            total = Decimal("0")
            for inst in due_soon:
                remaining = (
                    Decimal(str(inst.base_amount))
                    + Decimal(str(inst.late_fee_accrued))
                    - Decimal(str(inst.paid_amount))
                )
                total += remaining
                lines.append(
                    f"• {telegram_service.esc(inst.loan.client.name)} — parcela {inst.number} — "
                    f"R$ {remaining:.2f} — vence {inst.due_date.strftime('%d/%m/%Y')}"
                )
            lines.append(f"\nTotal a vencer: R$ {total:.2f}")
            telegram_service.send_message(
                settings_row.telegram_bot_token, settings_row.telegram_chat_id, "\n".join(lines)
            )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("due_soon_list_job falhou")
    finally:
        db.close()


def license_expiry_job() -> None:
    """Avisa diariamente no Telegram (e registra na auditoria) as empresas
    cuja licença vence em até LICENSE_WARNING_DAYS dias ou já venceu, para
    que renovem o plano com o administrador do sistema."""
    db = SessionLocal()
    try:
        today = date.today()
        horizon = today + timedelta(days=LICENSE_WARNING_DAYS)
        companies = (
            db.query(Company)
            .filter(Company.active.is_(True), Company.license_expires_at.isnot(None))
            .all()
        )
        for company in companies:
            expires_date = company.license_expires_at.date()
            if expires_date > horizon:
                continue
            settings_row = db.get(CompanyNotificationSettings, company.id)
            if not settings_row or not settings_row.telegram_bot_token or not settings_row.telegram_chat_id:
                continue
            if expires_date < today:
                text = (
                    f"🔒 <b>Licença expirada</b> ({telegram_service.esc(company.name)})\n"
                    f"Sua licença venceu em {expires_date.strftime('%d/%m/%Y')}.\n"
                    "Novos logins de gestores/consultores ficarão bloqueados. "
                    "Entre em contato com o administrador do sistema para renovar o plano."
                )
            else:
                days_left = (expires_date - today).days
                text = (
                    f"⚠️ <b>Licença vencendo</b> ({telegram_service.esc(company.name)})\n"
                    f"Sua licença vence em {expires_date.strftime('%d/%m/%Y')} "
                    f"({days_left} dia(s)).\n"
                    "Entre em contato com o administrador do sistema para renovar o plano."
                )
            telegram_service.send_message(settings_row.telegram_bot_token, settings_row.telegram_chat_id, text)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("license_expiry_job falhou")
    finally:
        db.close()


def backup_job() -> None:
    backup_service.run_backup()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(accrual_job, CronTrigger(hour=0, minute=5), id="accrual_job", replace_existing=True)
    scheduler.add_job(notify_job, CronTrigger(hour=8, minute=0), id="notify_job", replace_existing=True)
    scheduler.add_job(license_expiry_job, CronTrigger(hour=9, minute=0), id="license_expiry_job", replace_existing=True)
    scheduler.add_job(due_soon_list_job, CronTrigger(hour=12, minute=0), id="due_soon_list_job", replace_existing=True)
    scheduler.add_job(backup_job, CronTrigger(hour=2, minute=0), id="backup_job", replace_existing=True)
    scheduler.start()
    logger.info(
        "Agendador iniciado: accrual_job (00:05), notify_job (08:00), "
        "license_expiry_job (09:00), due_soon_list_job (12:00), backup_job (02:00)"
    )
    return scheduler
