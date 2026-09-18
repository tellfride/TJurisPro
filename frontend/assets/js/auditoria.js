(async function () {
  const user = requireAuth(["administrador", "gestor", "consultor"]);
  if (!user) return;
  if (user.role === "consultor" && !consultorPerm(user, "view_audit")) {
    window.location.href = "/clientes.html";
    return;
  }
  renderShell("auditoria.html");

  let companyFilter = "";
  let usersById = {};

  if (user.role === "administrador") {
    const select = document.getElementById("companyFilter");
    select.style.display = "inline-block";
    try {
      const companies = await api.get("/companies");
      select.innerHTML =
        '<option value="">Todas as empresas</option>' +
        companies.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
    } catch (e) {}
    select.addEventListener("change", () => {
      companyFilter = select.value;
      loadUsers().then(loadAudit);
    });
  }

  ["entityFilter", "dateFrom", "dateTo"].forEach((id) =>
    document.getElementById(id).addEventListener("change", loadAudit)
  );

  async function loadUsers() {
    const query = companyFilter ? `?company_id=${companyFilter}` : "";
    try {
      const users = await api.get(`/users${query}`);
      usersById = {};
      users.forEach((u) => (usersById[u.id] = u.name));
    } catch (e) {
      usersById = {};
    }
  }

  const ACTION_LABELS = {
    criar_empresa: "Criou empresa",
    editar_empresa: "Editou empresa",
    criar_usuario: "Criou usuário",
    editar_usuario: "Editou usuário",
    criar_cliente: "Criou cliente",
    editar_cliente: "Editou cliente",
    criar_emprestimo: "Lançou empréstimo",
    editar_emprestimo: "Editou empréstimo",
    registrar_pagamento: "Registrou pagamento",
    baixar_emprestimo: "Quitou empréstimo",
    cobranca_whatsapp: "Abriu cobrança no WhatsApp",
    editar_configuracao_notificacao: "Editou configuração de notificação",
    importar_planilha: "Importou planilha",
  };

  async function loadAudit() {
    const body = document.getElementById("auditBody");
    const query = new URLSearchParams();
    if (companyFilter) query.set("company_id", companyFilter);
    const entity = document.getElementById("entityFilter").value;
    if (entity) query.set("entity_type", entity);
    const dateFrom = document.getElementById("dateFrom").value;
    if (dateFrom) query.set("date_from", dateFrom);
    const dateTo = document.getElementById("dateTo").value;
    if (dateTo) query.set("date_to", dateTo);

    let logs;
    try {
      logs = await api.get(`/audit?${query.toString()}`);
    } catch (e) {
      body.innerHTML = `<tr><td colspan="5" class="empty-state">Erro ao carregar auditoria</td></tr>`;
      return;
    }

    if (logs.length === 0) {
      body.innerHTML = `<tr><td colspan="5" class="empty-state">Nenhum registro encontrado</td></tr>`;
      return;
    }

    body.innerHTML = logs
      .map((log) => {
        const when = new Date(log.created_at).toLocaleString("pt-BR");
        const userName = usersById[log.user_id] || (log.user_id ? `Usuário #${log.user_id}` : "Sistema");
        const action = ACTION_LABELS[log.action] || log.action;
        const details = log.details ? Object.entries(log.details).map(([k, v]) => `${k}: ${v}`).join(", ") : "-";
        return `
        <tr>
          <td>${when}</td>
          <td>${escapeHtml(userName)}</td>
          <td>${escapeHtml(action)}</td>
          <td>${escapeHtml(log.entity_type)}${log.entity_id ? " #" + log.entity_id : ""}</td>
          <td class="text-muted" style="font-size:0.8rem;">${escapeHtml(details)}</td>
        </tr>`;
      })
      .join("");
  }

  await loadUsers();
  loadAudit();
})();
