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
  por atraso — tudo definido pelo operador/gestor. Cada empréstimo recebe um
  **número de ordem sequencial por empresa**, mesmo que o cliente já tenha
  outro empréstimo.
- **Parcelas mensais** geradas automaticamente, com multa por atraso
  recalculada todo dia a partir dos dias corridos de atraso.
- **Pagamento parcial só dos juros/multa** ("pagar só os juros"), sem
  precisar quitar a parcela inteira.
- **Quitação antecipada** com valor final ajustável pelo gestor.
- **Dashboard** (Gestor/Administrador, oculto para Operador): saldo
  emprestado, total a receber, lucro de juros e de multa (mês e total),
  próximos vencimentos (5 e 15 dias), quem mais pega emprestado, quem mais
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
  empresa) → Operador (cadastra cliente/empréstimo, registra pagamento, sem
  acesso a dashboard/auditoria).

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
> vez rodando o sistema), também rode `python migrate_v2.py` e
> `python migrate_v3.py` uma vez — eles adicionam colunas novas em tabelas
> que já existiam antes dessas funcionalidades (idempotente, pode rodar
> mais de uma vez sem erro).

## 5. Rodar o sistema

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Acesse **http://localhost:8000** e faça login com o Administrador.

## 6. Estrutura de uso

1. **Administrador** cadastra as empresas (aba Administração) e os usuários
   Gestor/Operador de cada uma.
2. **Operador** cadastra clientes e lança empréstimos.
3. **Gestor** acompanha o Dashboard, edita taxa/multa, registra quitações
   antecipadas e acessa a Auditoria da própria empresa.
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
frontend/           # site estático (HTML/CSS/JS puro), servido pelo próprio backend
backups/            # saída dos backups diários do MySQL
```

## Papéis e permissões

| Ação | Administrador | Gestor | Operador |
|---|---|---|---|
| Ver todas as empresas | ✅ | ❌ (só a própria) | ❌ (só a própria) |
| Cadastrar cliente / empréstimo | — | ✅ | ✅ |
| Importar planilha em massa | — | ✅ | ✅ |
| Editar taxa de juros / multa | ✅ | ✅ | ❌ |
| Quitar (baixar) empréstimo | ✅ | ✅ | ❌ |
| Ver Dashboard | ✅ | ✅ | ❌ (bloqueado) |
| Ver Auditoria | ✅ (todas) | ✅ (própria empresa) | ❌ |
| Exportar relatórios | ✅ | ✅ | ❌ |
| Enviar cobrança via WhatsApp | ✅ | ✅ | ✅ |
| Cadastrar empresas/usuários | ✅ | Só operadores da própria empresa | ❌ |
