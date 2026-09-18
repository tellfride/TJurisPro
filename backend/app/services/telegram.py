import html
import logging

import requests
from sqlalchemy.orm import Session

from ..models import CompanyNotificationSettings

logger = logging.getLogger("jurispro.telegram")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT_SECONDS = 10


def esc(value) -> str:
    """Escapa texto vindo do usuário (nome de cliente, de empresa...) antes de
    colocá-lo numa mensagem com parse_mode HTML. Sem isso, um cliente cadastrado
    como `<a href="http://golpe">clique</a>` vira link clicável dentro do grupo do
    Telegram da empresa — e um `<` solto faz o Telegram recusar a mensagem inteira."""
    return html.escape(str(value), quote=False)


def send_message(bot_token: str, chat_id: str, text: str) -> bool:
    try:
        response = requests.post(
            TELEGRAM_API.format(token=bot_token),
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            logger.warning("Falha ao enviar mensagem Telegram: %s", response.text)
            return False
        return True
    except requests.RequestException as exc:
        # Não logar `exc`: a mensagem do requests traz a URL completa, que contém
        # o token do bot (/bot<TOKEN>/sendMessage).
        logger.warning("Erro de rede ao enviar mensagem Telegram (%s)", type(exc).__name__)
        return False


def notify_company(db: Session, company_id: int, text: str) -> bool:
    settings_row = db.get(CompanyNotificationSettings, company_id)
    if not settings_row or not settings_row.telegram_bot_token or not settings_row.telegram_chat_id:
        logger.info("Telegram não configurado para a empresa %s — notificação ignorada", company_id)
        return False
    return send_message(settings_row.telegram_bot_token, settings_row.telegram_chat_id, text)
