import logging
from datetime import date, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..database import SessionLocal
from ..models import Company, CompanyNotificationSettings, Installment, InstallmentStatus, NotificationLog
from . import backup as backup_service
from . import telegram as telegram_service
from .interest_engine import recompute_overdue_installments

logger = logging.getLogger("jurispro.scheduler")

DUE_SOON_TYPE = "vencimento_proximo"


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
                    f"Cliente: {client_name}\n"
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


def backup_job() -> None:
    backup_service.run_backup()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(accrual_job, CronTrigger(hour=0, minute=5), id="accrual_job", replace_existing=True)
    scheduler.add_job(notify_job, CronTrigger(hour=8, minute=0), id="notify_job", replace_existing=True)
    scheduler.add_job(backup_job, CronTrigger(hour=2, minute=0), id="backup_job", replace_existing=True)
    scheduler.start()
    logger.info("Agendador iniciado: accrual_job (00:05), notify_job (08:00), backup_job (02:00)")
    return scheduler
