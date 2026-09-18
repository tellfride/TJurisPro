# JurisPRO

Sistema de cobrança com juros, multi-empresa, com dashboards, auditoria,
notificações via Telegram, envio de cobrança via WhatsApp, importação e
exportação em planilha, e backup diário automático.

- **Backend**: Python (FastAPI) + MySQL
- **Frontend**: HTML/CSS/JS puro (sem Node, sem build), tema claro/escuro,
  responsivo para celular e PC.

---

## Funcionalidades

- **Cadastro de cliente**: nome, CPF (com validação de dígito verificador),
  telefone, email, endereço com **preenchimento automático pelo CEP** (só
  falta o número do imóvel), e até 3 contatos de referência.
- **Empréstimos**: valor, taxa de juros do período, prazo em meses e multa
  por atraso — tudo definido pelo consultor/gestor. Cada empréstimo recebe um
  **número de ordem sequencial por empresa**, mesmo que o cliente já tenha
  outro empréstimo.
- **Parcelas mensais** geradas automaticamente, com multa por atraso
  recalculada todo dia a partir dos dias corridos de atraso.
- **Pagamento parcial só dos juros/multa** ("pagar só os juros"), sem
  precisar quitar a parcela inteira.
- **Quitação antecipada** com valor final ajustável pelo gestor.
- **Dashboard** (Gestor/Administrador, e Consultor se liberado): saldo
  emprestado, total a receber, lucro de juros e de multa (mês e total),
  próximos vencimentos (3, 5 e 15 dias), quem mais pega emprestado, quem mais
  e quem menos atrasa — todos os cards são clicáveis.
- **Envio de cobrança via WhatsApp**: gera a mensagem e abre o WhatsApp Web
  já com o texto pronto pra enviar (não manda sozinho).
- **Notificação automática via Telegram**: aviso de vencimento próximo
  (configurável por empresa) e aviso a cada novo cliente/empréstimo
  cadastrado.
- **Auditoria completa**: todo cadastro, edição, pagamento e quitação fica
  registrado (quem, quando, o quê).
- **Relatórios**: exportação de todo o histórico de transações em `.xlsx`.
- **Importação em massa**: cadastro de vários clientes e empréstimos de uma
  vez só, a partir de uma planilha `.xlsx` (com modelo pra baixar).
- **Backup diário automático** do banco MySQL.
- **Permissões**: Administrador (acesso total, todas as empresas) → Gestor
  (edita taxa/multa, quita empréstimo, vê dashboard/auditoria da própria
  empresa, gerencia a equipe na aba **Particionamento**) → **Consultor**
  (acesso configurável — o gestor liga/desliga, campo a campo, o que cada
  consultor pode ver/fazer na aba Particionamento: de cadastrar
  cliente/empréstimo/pagamento e mandar WhatsApp — o padrão — até Dashboard,
  Relatórios, Auditoria, editar taxa/multa e quitar empréstimo).
- **Licenciamento por empresa**: o Administrador define, por empresa, até
  quando a licença vale e um limite de clientes cadastrados. Login de
  gestor/consultor é bloqueado quando a licença vence, e a empresa é
  avisada (banner no sistema + Telegram) a partir de 7 dias antes de vencer.
- **Segurança de login**: 1 sessão ativa por usuário (logar em outro
  aparelho encerra a sessão anterior), bloqueio de 5 minutos após 3 senhas
  erradas seguidas — tanto **por conta** quanto **por endereço IP** (mesmo
  que o robô tente senhas em contas diferentes a partir do mesmo IP, ou
  acerte a senha depois de errar 3x, o IP fica bloqueado do mesmo jeito) —,
  e mensagens claras de erro (senha incorreta, conta bloqueada, licença
  expirada).
- **Modelos de mensagem WhatsApp**: cada empresa cadastra os próprios
  modelos (com placeholders tipo `{{cliente}}`, `{{valor}}`) na aba
  Configurações, prontos pra escolher (ou personalizar na hora) sempre que
  for mandar uma cobrança.

## 1. Pré-requisitos

- **Python 3.11+** instalado.
- **MySQL Server** (ou MariaDB, 100% compatível) rodando.
- **mysqldump** disponível (já vem junto com qualquer instalação do MySQL/MariaDB) —
  necessário para o backup diário automático.

## 2. Criar o banco de dados MySQL

```sql
CREATE DATABASE jurispro CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'jurispro'@'%' IDENTIFIED BY 'uma-senha-forte-aqui';
GRANT ALL PRIVILEGES ON jurispro.* TO 'jurispro'@'%';
FLUSH PRIVILEGES;
```

## 3. Configurar o backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env       # Linux/Mac: cp .env.example .env
```

Edite `backend/.env` com os dados de conexão do banco (passo 2), um
`JWT_SECRET` aleatório, e o email/senha do primeiro Administrador.

## 4. Criar as tabelas e o primeiro Administrador

```bash
python seed.py
```

Cria automaticamente todas as tabelas e o usuário Administrador definido no
`.env`. Rode só uma vez (rodar de novo não duplica nada).

> Se você estiver atualizando uma instalação já existente (não é a primeira
> vez rodando o sistema), também rode `python migrate_v2.py`,
> `python migrate_v3.py`, `python migrate_v4.py` e `python migrate_v5.py`
> uma vez — eles adicionam colunas/tabelas novas e migram usuários Operador
> (descontinuado) para Consultor (idempotente, pode rodar mais de uma vez
> sem erro).

## 5. Rodar o sistema

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Acesse **http://localhost:8000** e faça login com o Administrador.

## 6. Estrutura de uso

1. **Administrador** cadastra as empresas (aba Administração), define a
   licença/limite de clientes de cada uma, e os usuários Gestor de cada uma.
2. **Gestor** acompanha o Dashboard, edita taxa/multa, registra quitações
   antecipadas, acessa a Auditoria da própria empresa, e cadastra os
   **Consultores** da sua equipe na aba **Particionamento** — escolhendo ali
   exatamente o que cada consultor pode ver/fazer.
3. **Consultor** cadastra clientes e lança empréstimos (e o que mais o
   gestor liberar para ele).
4. Cada empresa configura seu próprio bot do Telegram em **Configurações**.

## 7. Configurar as notificações do Telegram

1. Converse com **@BotFather** no Telegram, envie `/newbot` e siga as
   instruções. Copie o **token** gerado.
2. Crie um grupo, adicione o bot a ele.
3. Para achar o **Chat ID**: adicione o bot **@userinfobot** temporariamente,
   ou abra `https://api.telegram.org/bot<TOKEN>/getUpdates` depois de mandar
   uma mensagem qualquer no grupo — o `chat.id` aparece no JSON.
4. Em **Configurações**, cole o token e o chat ID, defina os dias de
   antecedência do aviso, e salve.

## 8. Backup diário

Todo dia às 02:00 (horário de São Paulo) o sistema roda `mysqldump`
automaticamente e salva em `backups/`, mantendo os últimos
`BACKUP_RETENTION_DAYS` dias (30 por padrão). O processo do `uvicorn`
precisa ficar rodando continuamente pros agendamentos (juros às 00:05,
notificações às 08:00, backup às 02:00) funcionarem — recomendado rodar
como serviço (Tarefa Agendada/NSSM no Windows, `systemd` no Linux).

## 9. Hospedagem

Precisa de um lugar que rode um processo Python continuamente + MySQL —
hospedagem de site estático não serve. Funciona bem em qualquer VPS Linux
(Hostinger, Locaweb, DigitalOcean, etc.) ou em plataformas de "app sempre
ativo" (Railway, Render, Fly.io).

## 10. Estrutura de pastas

```
backend/            # API (FastAPI) + regras de negócio + agendador
  app/
    routers/          # endpoints da API
    services/          # motor de juros, Telegram, backup, agendador, auditoria, validação de CPF
  seed.py              # cria as tabelas + primeiro Administrador
  migrate_v2.py        # migração: referências do cliente + número de ordem do empréstimo
  migrate_v3.py        # migração: CEP + número do endereço
  migrate_v4.py        # migração: licença/limite por empresa, papel Consultor, sessão única, bloqueio de login
  migrate_v5.py        # migração: descontinua o papel Operador (migrado para Consultor equivalente)
frontend/           # site estático (HTML/CSS/JS puro), servido pelo próprio backend
backups/            # saída dos backups diários do MySQL
```

## Papéis e permissões

| Ação | Administrador | Gestor | Consultor |
|---|---|---|---|
| Ver todas as empresas | ✅ | ❌ (só a própria) | ❌ (só a própria) |
| Cadastrar cliente / empréstimo | — | ✅ | Configurável (padrão: ✅) |
| Importar planilha em massa | — | ✅ | Configurável |
| Registrar pagamento | — | ✅ | Configurável (padrão: ✅) |
| Editar taxa de juros / multa | ✅ | ✅ | Configurável (padrão: ❌) |
| Quitar (baixar) empréstimo | ✅ | ✅ | Configurável (padrão: ❌) |
| Ver Dashboard | ✅ | ✅ | Configurável (padrão: ❌) |
| Ver Auditoria | ✅ (todas) | ✅ (própria empresa) | Configurável (padrão: ❌) |
| Exportar relatórios | ✅ | ✅ | Configurável (padrão: ❌) |
| Enviar cobrança via WhatsApp | ✅ | ✅ | Configurável (padrão: ✅) |
| Cadastrar empresas/usuários | ✅ | Consultores da própria empresa (aba Particionamento) | ❌ |

"Configurável" = o gestor liga/desliga essa permissão pra cada consultor,
individualmente, na aba **Particionamento**.
