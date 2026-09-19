# Política de Segurança — JurisPRO

## Como relatar uma vulnerabilidade

Não abra uma *issue* pública com detalhes de falha. Use **Security → Report a vulnerability**
neste repositório (relato privado do GitHub) e informe: o que acontece, passos para reproduzir,
o impacto e a versão (commit). Depois da correção, o relato pode ser divulgado.

## Versões com correção de segurança

Apenas a versão mais recente da branch `main`.

## Políticas em vigor

Valores abaixo são os do código; a auditoria de 18/09/2026 e os testes estão descritos nos commits.

### Contas e sessões
- **Senha:** 8 a 128 caracteres ao criar ou trocar. Contas antigas com senha menor continuam entrando.
- **Bloqueio:** 3 erros bloqueiam a conta por 5 minutos; 3 erros vindos do mesmo IP bloqueiam o IP por
  5 minutos. No nginx, o login é limitado a 5 por minuto por IP.
- **Sessão:** uma por usuário (novo login encerra o anterior). "Sair" encerra a sessão no servidor
  (`POST /api/auth/logout`). Token JWT HS256 de 8 h (`JWT_EXPIRE_HOURS`).
- **Segredo:** `JWT_SECRET` é obrigatório e precisa ter 32 caracteres ou mais; sem isso o servidor não inicia.
- **Licença:** empresa com licença vencida não entra (exceto o administrador).

### Isolamento entre empresas
Toda consulta confere a empresa (`company_id`) no servidor. Papéis: administrador, gestor e consultor
(este com permissões liberadas uma a uma pelo gestor).

### Entradas e arquivos
- **Campos:** todo texto tem tamanho máximo igual ao da coluna do banco. Valores: principal até R$ 100 milhões,
  juros até 1000 %, multa até R$ 100 mil por dia, pagamento até R$ 1 bilhão, prazo até 120 meses.
  Números como `Infinity` ou `NaN` são recusados.
- **Erros de validação (422):** devolvem só onde está o erro; nunca o valor enviado.
- **Importação de planilha (.xlsx):** até 5 MB, assinatura ZIP conferida, no máximo 50 MB e 200 arquivos
  depois de descompactar, e até 1000 linhas com dado (`IMPORT_MAX_ROWS`). A contagem é feita antes de gravar.
  Erros inesperados vão para o log, sem SQL na resposta.
- **Exportação (.xlsx):** texto que começa com `=`, `+`, `-` ou `@` é gravado como texto, nunca como fórmula.
- **Telegram:** nomes digitados são escapados nas mensagens; o token do bot aparece mascarado na API e
  nunca é registrado em log.

### Interface, cabeçalhos e rede
- **CSP:** só scripts do próprio site (`script-src 'self'`); a única chamada externa permitida é o ViaCEP.
  A política completa e os demais cabeçalhos estão em [`deploy/nginx/security-headers.conf`](deploy/nginx/security-headers.conf).
- HSTS de 1 ano, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy` e
  `Permissions-Policy`. Respostas de `/api/` levam `Cache-Control: no-store`.
- A documentação interativa da API (`/docs`, `/redoc`, `/openapi.json`) fica desligada; use `ENABLE_DOCS=true`
  só em desenvolvimento.
- No nginx: corpo de requisição de 1 MB (6 MB só na importação) e limite de taxa por IP em `/api/`.

### Segredos, dados e dependências
- `.env` e `app.env` ficam fora do git, com permissão 600. O contêiner web recebe `app.env`, que **não**
  contém `MYSQL_ROOT_PASSWORD` nem `ADMIN_PASSWORD`.
- Backups do banco com permissão 600; a senha do banco vai para o `mysqldump` por variável de ambiente,
  nunca na linha de comando.
- Dependências com versão fixada em `backend/requirements.txt`. `pip-audit` sem achados em 18/09/2026;
  reexecute antes de cada publicação.
