(async function () {
  const user = requireAuth(["administrador", "gestor"]);
  if (!user) return;
  renderShell("dashboard.html");

  let companyFilter = "";

  if (user.role === "administrador") {
    document.getElementById("companyFilterWrap").style.display = "block";
    const select = document.getElementById("companyFilter");
    try {
      const companies = await api.get("/companies");
      select.innerHTML =
        '<option value="">Todas as empresas</option>' +
        companies.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
    } catch (e) {
      select.innerHTML = '<option value="">Todas as empresas</option>';
    }
    select.addEventListener("change", () => {
      companyFilter = select.value;
      loadDashboard();
    });
  }

  function loanLink(extra) {
    const query = new URLSearchParams(extra || {});
    if (companyFilter) query.set("company_id", companyFilter);
    const qs = query.toString();
    return "/emprestimos.html" + (qs ? "?" + qs : "");
  }

  function clientLink(clientId, clientName) {
    const query = new URLSearchParams({ client_id: clientId, client_name: clientName || "" });
    if (companyFilter) query.set("company_id", companyFilter);
    return "/emprestimos.html?" + query.toString();
  }

  async function loadDashboard() {
    const query = companyFilter ? `?company_id=${companyFilter}` : "";
    let data;
    try {
      data = await api.get(`/dashboard${query}`);
    } catch (e) {
      return;
    }

    document.getElementById("statOutstanding").textContent = formatMoney(data.total_outstanding_balance);
    document.getElementById("statToReceive").textContent = formatMoney(data.total_to_receive);
    document.getElementById("statActive").textContent = data.active_loans;
    document.getElementById("statOverdue").textContent = data.overdue_loans;
    document.getElementById("statSettled").textContent = data.settled_loans;
    document.getElementById("statMonthlyProfit").textContent = formatMoney(data.monthly_profit);
    document.getElementById("statInterestProfit").textContent = formatMoney(data.interest_profit_total);
    document.getElementById("statLateFeeProfit").textContent = formatMoney(data.late_fee_profit_total);

    document.getElementById("cardOutstanding").href = loanLink();
    document.getElementById("cardToReceive").href = loanLink();
    document.getElementById("cardActive").href = loanLink({ status: "ativo" });
    document.getElementById("cardOverdue").href = loanLink({ status: "atrasado" });
    document.getElementById("cardSettled").href = loanLink({ status: "quitado" });
    const relatoriosLink = "/relatorios.html" + (companyFilter ? `?company_id=${companyFilter}` : "");
    document.getElementById("cardMonthlyProfit").href = relatoriosLink;
    document.getElementById("cardInterestProfit").href = relatoriosLink;
    document.getElementById("cardLateFeeProfit").href = relatoriosLink;

    const in5Days = new Date();
    in5Days.setHours(0, 0, 0, 0);
    in5Days.setDate(in5Days.getDate() + 5);
    const upcoming5d = data.upcoming_installments.filter((i) => new Date(i.due_date + "T00:00:00") <= in5Days);

    renderUpcomingTable("upcoming5Body", upcoming5d, "Nenhum vencimento nos próximos 5 dias 🎉");
    renderUpcomingTable("upcomingBody", data.upcoming_installments, "Nenhum vencimento nos próximos 15 dias");

    renderBarList("topClientsWrap", data.top_clients, {
      empty: "Sem empréstimos cadastrados ainda",
      valueOf: (c) => c.total_borrowed,
      barColor: "var(--color-accent)",
      row: (c) => ({
        href: clientLink(c.client_id, c.client_name),
        label: `${escapeHtml(c.client_name)} <span class="text-muted">(${c.loan_count} empréstimo${c.loan_count > 1 ? "s" : ""})</span>`,
        value: formatMoney(c.total_borrowed),
      }),
    });

    renderBarList("mostDelinquentWrap", data.most_delinquent_clients, {
      empty: "Nenhum cliente com parcelas atrasadas 🎉",
      valueOf: (c) => c.late_installments,
      barColor: "var(--color-danger)",
      row: (c) => ({
        href: clientLink(c.client_id, c.client_name),
        label: `${escapeHtml(c.client_name)} <span class="text-muted">(${c.late_installments} de ${c.total_installments} parcelas)</span>`,
        value: `${c.late_installments}`,
      }),
    });

    renderBarList("bestPayersWrap", data.best_payers, {
      empty: "Sem dados suficientes ainda",
      valueOf: (c) => c.total_installments - c.late_installments,
      barColor: "var(--color-success)",
      row: (c) => ({
        href: clientLink(c.client_id, c.client_name),
        label: `${escapeHtml(c.client_name)} <span class="text-muted">(${c.late_installments} de ${c.total_installments} parcelas atrasadas)</span>`,
        value: c.late_installments === 0 ? "Em dia" : `${c.late_installments} atraso(s)`,
      }),
    });
  }

  function renderUpcomingTable(bodyId, installments, emptyMessage) {
    const body = document.getElementById(bodyId);
    if (installments.length === 0) {
      body.innerHTML = `<tr><td colspan="5" class="empty-state">${emptyMessage}</td></tr>`;
      return;
    }
    body.innerHTML = installments
      .map(
        (i) => `
      <tr>
        <td>${escapeHtml(i.client_name)}</td>
        <td><a href="/emprestimo_detalhe.html?id=${i.loan_id}">Empréstimo Nº ${i.loan_number}</a></td>
        <td>${formatDate(i.due_date)}</td>
        <td>${formatMoney(i.amount)}</td>
        <td class="text-right">
          ${i.client_phone ? `<button class="btn btn-sm btn-outline whatsapp-btn" data-installment-id="${i.installment_id}" title="Enviar lembrete via WhatsApp">💬</button>` : ""}
        </td>
      </tr>`
      )
      .join("");

    body.querySelectorAll(".whatsapp-btn").forEach((btn) => {
      const inst = installments.find((i) => String(i.installment_id) === btn.dataset.installmentId);
      btn.addEventListener("click", () => {
        const message = buildDueSoonMessage(inst.client_name, inst.due_date, inst.amount);
        if (!openWhatsApp(inst.client_phone, message)) {
          alert("Telefone do cliente inválido ou não cadastrado.");
        }
      });
    });
  }

  function renderBarList(elementId, items, opts) {
    const wrap = document.getElementById(elementId);
    if (!items || items.length === 0) {
      wrap.innerHTML = `<div class="empty-state">${opts.empty}</div>`;
      return;
    }
    const max = Math.max(...items.map(opts.valueOf), 1);
    wrap.innerHTML = items
      .map((item) => {
        const row = opts.row(item);
        const pct = Math.round((opts.valueOf(item) / max) * 100);
        return `
        <a class="bar-row" href="${row.href}">
          <div class="flex-between" style="font-size:0.85rem;">
            <span>${row.label}</span>
            <strong>${row.value}</strong>
          </div>
          <div style="background:var(--color-surface-alt);border-radius:999px;height:8px;margin-top:4px;overflow:hidden;">
            <div style="width:${pct}%;background:${opts.barColor};height:100%;"></div>
          </div>
        </a>`;
      })
      .join("");
  }

  loadDashboard();
})();
