"""Modelos de cobrança via WhatsApp já prontos para cada empresa.

Usam só os campos que TODA tela preenche ao abrir o compositor de mensagens
({{cliente}}, {{valor}}, {{vencimento}}, {{emprestimo}}) — o botão 💬 do
dashboard, por exemplo, não informa {{parcela}}, e um placeholder sem valor
apareceria cru na mensagem. Depois de criados, o gestor edita/exclui como
qualquer outro modelo (Configurações) e escolhe qual usar ao cobrar.
"""

from sqlalchemy.orm import Session

from ..models import WhatsappTemplate

DEFAULT_TEMPLATES: list[tuple[str, str]] = [
    (
        "Lembrete de vencimento (amigável)",
        "Olá, {{cliente}}! Tudo bem? 😊 Passando para lembrar que a sua parcela do empréstimo "
        "Nº {{emprestimo}}, no valor de {{valor}}, vence em {{vencimento}}. Se precisar de "
        "qualquer ajuda ou da forma de pagamento, é só me chamar por aqui. Obrigado!",
    ),
    (
        "Vence hoje",
        "Olá, {{cliente}}! Lembrete: a sua parcela do empréstimo Nº {{emprestimo}} vence hoje "
        "({{vencimento}}), no valor de {{valor}}. Se já efetuou o pagamento, por favor "
        "desconsidere esta mensagem. Obrigado!",
    ),
    (
        "Parcela em atraso — 1º aviso",
        "Olá, {{cliente}}! Identificamos que a parcela do empréstimo Nº {{emprestimo}}, com "
        "vencimento em {{vencimento}}, ainda está em aberto. O valor atualizado é de {{valor}}. "
        "Poderia regularizar o pagamento? Se já pagou, envie o comprovante para conferirmos. "
        "Ficamos à disposição!",
    ),
    (
        "Cobrança em atraso — firme",
        "{{cliente}}, a parcela do seu empréstimo Nº {{emprestimo}} está em atraso desde "
        "{{vencimento}}, e o valor atualizado com a multa por atraso é de {{valor}}. Pedimos que "
        "regularize o pagamento o quanto antes para evitar novos acréscimos. Caso precise "
        "conversar sobre o pagamento, responda esta mensagem.",
    ),
    (
        "Proposta de negociação",
        "Olá, {{cliente}}! Sabemos que imprevistos acontecem. Sobre a parcela do empréstimo "
        "Nº {{emprestimo}} (vencida em {{vencimento}}, valor atualizado {{valor}}), gostaríamos "
        "de encontrar a melhor forma de regularizar com você. Podemos conversar sobre uma "
        "condição de pagamento? Aguardamos seu retorno.",
    ),
    (
        "Agradecimento pelo pagamento",
        "Olá, {{cliente}}! Confirmamos o recebimento do seu pagamento referente ao empréstimo "
        "Nº {{emprestimo}}. Muito obrigado pela pontualidade e pela confiança! Qualquer dúvida, "
        "estamos à disposição.",
    ),
]


def ensure_default_templates(db: Session, company_id: int) -> list[WhatsappTemplate]:
    """Cria, para a empresa, os modelos padrão que ainda não existem (compara
    pelo nome, sem diferenciar maiúsculas). Idempotente. Não faz commit."""
    existing = {
        name.strip().lower()
        for (name,) in db.query(WhatsappTemplate.name).filter(WhatsappTemplate.company_id == company_id)
    }
    created: list[WhatsappTemplate] = []
    for name, content in DEFAULT_TEMPLATES:
        if name.lower() in existing:
            continue
        template = WhatsappTemplate(company_id=company_id, name=name, content=content)
        db.add(template)
        created.append(template)
    db.flush()
    return created
