(async function () {
  const user = requireAuth(["administrador", "gestor", "consultor"]);
  if (!user) return;
  renderShell("emprestimos.html");

  const isAdminOrGestor = user.role === "administrador" || user.role === "gestor";
  const canEditRate = isAdminOrGestor || (user.role === "consultor" && consultorPerm(user, "edit_rates"));
  const canSettle = isAdminOrGestor || (user.role === "consultor" && consultorPerm(user, "settle_loans"));
  const canRegisterPayment = consultorPerm(user, "register_payments");
  const canSendWhatsapp = consultorPerm(user, "send_whatsapp");

  const params = new URLSearchParams(window.location.search);
  const loanId = params.get("id");
  if (!loanId) {
    window.location.href = "/emprestimos.html";
    return;
  }

  let loan = null;

  async function loadLoan() {
    try {
      loan = await api.get(`/loans/${loanId}`);
    } catch (e) {
      document.getElementById("loanSummaryCard").innerHTML = `<div class="empty-state">Empréstimo não encontrado</div>`;
      return;
    }
    renderSummary();
    renderContactCard();
    renderActions();
    renderInstallments();
    renderPayments();
    loadHistory();
  }

  // ---------- Histórico da OS (linha do tempo) ----------
  const HISTORY_KINDS = {
    aberta: { icon: "🧾", title: "OS aberta" },
    pagamento: { icon: "💵", title: "Pagamento registrado" },
    quitacao: { icon: "✅", title: "Quitação antecipada" },
    edicao: { icon: "✏️", title: "Juros/multa ajustados" },
    cobranca_whatsapp: { icon: "💬", title: "Cobrança via WhatsApp" },
  };

  // Devolve HTML — todo texto vindo do banco passa por escapeHtml aqui.
  function historyDescription(kind, d) {
    d = d || {};
    if (kind === "aberta") {
      return (
        `${escapeHtml(d.client)} · ${formatMoney(d.principal)} a ${Number(d.interest_rate).toFixed(2)}% em ${Number(d.term_months)}x` +
        ` · total ${formatMoney(d.total_amount)} · multa ${formatMoney(d.late_fee_per_day)}/dia`
      );
    }
    if (kind === "pagamento") {
      const fee = Number(d.late_fee_included) > 0 ? ` (inclui ${formatMoney(d.late_fee_included)} de multa)` : "";
      const notes = d.notes ? ` · ${escapeHtml(d.notes)}` : "";
      return `${formatMoney(d.amount)} na parcela ${Number(d.installment_number)}${fee} · pago em ${formatDate(d.payment_date)}${notes}`;
    }
    if (kind === "quitacao") {
      const notes = d.notes ? ` · ${escapeHtml(d.notes)}` : "";
      return `${formatMoney(d.amount)} · em ${formatDate(d.payment_date)}${notes}`;
    }
    if (kind === "edicao") {
      const parts = [];
      if (d.interest_rate != null) parts.push(`juros ${Number(d.interest_rate).toFixed(2)}%`);
      if (d.late_fee_per_day != null) parts.push(`multa ${formatMoney(d.late_fee_per_day)}/dia`);
      return parts.length ? `Novos valores: ${parts.join(" · ")}` : "";
    }
    if (kind === "cobranca_whatsapp") {
      const message = String(d.message || "");
      const shown = message.length > 300 ? message.slice(0, 300) + "…" : message;
      return (
        `${d.template ? `Modelo: ${escapeHtml(d.template)}` : "Mensagem automática/personalizada"}` +
        `<div class="tl-msg">${escapeHtml(shown)}</div>`
      );
    }
    return "";
  }

  function renderHistoryEvent(e) {
    const meta = HISTORY_KINDS[e.kind] || { icon: "•", title: escapeHtml(e.kind) };
    const who = e.user_name ? ` · ${escapeHtml(e.user_name)}` : "";
    return `
      <li>
        <span class="tl-icon">${meta.icon}</span>
        <div class="tl-body">
          <div class="flex-between" style="gap:0.75rem;flex-wrap:wrap;">
            <span class="tl-title">${meta.title}</span>
            <span class="tl-meta">${formatDateTime(e.at)}${who}</span>
          </div>
          <div class="tl-desc">${historyDescription(e.kind, e.data)}</div>
        </div>
      </li>`;
  }

  async function loadHistory() {
    const list = document.getElementById("historyList");
    try {
      const events = await api.get(`/loans/${loanId}/history`);
      list.innerHTML = events.length
        ? events.map(renderHistoryEvent).join("")
        : `<li class="empty-state">Nenhum evento registrado</li>`;
    } catch (e) {
      list.innerHTML = `<li class="empty-state">Não foi possível carregar o histórico</li>`;
    }
  }

  function renderSummary() {
    document.getElementById("loanSummaryCard").innerHTML = `
      <div class="flex-between" style="flex-wrap:wrap;gap:0.75rem;">
        <div>
          <h2 style="margin-bottom:0.2rem;">${escapeHtml(loan.client.name)}</h2>
          <div class="text-muted" style="font-size:0.85rem;">Ordem de serviço <strong>${formatOsNumber(loan.loan_number)}</strong> · lançada em ${parseUtc(loan.created_at).toLocaleDateString("pt-BR")}</div>
        </div>
        <span class="status-pill status-${loan.status}" style="font-size:0.85rem;">${statusLabel(loan.status)}</span>
      </div>
      <div class="field-row mt-2">
        <div><div class="text-muted" style="font-size:0.78rem;">Valor solicitado</div><strong>${formatMoney(loan.principal)}</strong></div>
        <div><div class="text-muted" style="font-size:0.78rem;">Juros do período</div><strong>${Number(loan.interest_rate).toFixed(2)}%</strong></div>
        <div><div class="text-muted" style="font-size:0.78rem;">Prazo</div><strong>${loan.term_months}x</strong></div>
        <div><div class="text-muted" style="font-size:0.78rem;">Multa por atraso</div><strong>${formatMoney(loan.late_fee_per_day)}/dia</strong></div>
        <div><div class="text-muted" style="font-size:0.78rem;">Total contratado</div><strong>${formatMoney(loan.total_amount)}</strong></div>
        ${loan.payoff_amount ? `<div><div class="text-muted" style="font-size:0.78rem;">Valor da quitação</div><strong>${formatMoney(loan.payoff_amount)}</strong></div>` : ""}
      </div>
    `;
  }

  function renderContactCard() {
    const c = loan.client;
    const references = [
      [c.reference1_name, c.reference1_phone],
      [c.reference2_name, c.reference2_phone],
      [c.reference3_name, c.reference3_phone],
    ].filter(([name, phone]) => name || phone);

    const refsHtml = references.length
      ? references
          .map(
            ([name, phone]) =>
              `<div><div class="text-muted" style="font-size:0.78rem;">${escapeHtml(name || "Referência")}</div><strong>${escapeHtml(phone || "-")}</strong></div>`
          )
          .join("")
      : "";

    const fullAddress = [c.address, c.address_number ? `Nº ${c.address_number}` : "", c.cep ? `CEP ${c.cep}` : ""]
      .filter(Boolean)
      .join(", ");

    document.getElementById("clientContactCard").innerHTML = `
      <h3 style="margin-bottom:0.6rem;">Dados de contato</h3>
      <div class="field-row">
        <div><div class="text-muted" style="font-size:0.78rem;">CPF</div><strong>${escapeHtml(c.document || "-")}</strong></div>
        <div><div class="text-muted" style="font-size:0.78rem;">Telefone</div><strong>${escapeHtml(c.phone || "-")}</strong></div>
        <div><div class="text-muted" style="font-size:0.78rem;">Endereço</div><strong>${escapeHtml(fullAddress || "-")}</strong></div>
      </div>
      ${refsHtml ? `<div class="field-row mt-1">${refsHtml}</div>` : ""}
    `;
  }

  function renderActions() {
    const actions = document.getElementById("loanActions");
    const buttons = [];
    if (loan.status !== "quitado" && canEditRate) {
      buttons.push(`<button class="btn btn-outline" id="editLoanBtn">Editar taxa/multa</button>`);
    }
    if (loan.status !== "quitado" && canSettle) {
      buttons.push(`<button class="btn btn-accent" id="payoffBtn">Quitar antecipadamente</button>`);
    }
    if (loan.client.phone && canSendWhatsapp) {
      buttons.push(`<button class="btn btn-whatsapp" id="whatsappBtn">💬 Cobrar via WhatsApp</button>`);
    }
    actions.innerHTML = buttons.join("");
    if (loan.status !== "quitado" && canEditRate) {
      document.getElementById("editLoanBtn").addEventListener("click", openEditLoanModal);
    }
    if (loan.status !== "quitado" && canSettle) {
      document.getElementById("payoffBtn").addEventListener("click", openPayoffModal);
    }
    if (loan.client.phone && canSendWhatsapp) {
      document.getElementById("whatsappBtn").addEventListener("click", () => openLoanCollectionComposer(loan, loadHistory));
    }
  }

  function renderInstallments() {
    const body = document.getElementById("installmentsBody");
    body.innerHTML = loan.installments
      .map((i) => {
        const due = i.base_amount + i.late_fee_accrued - i.paid_amount;
        const canPay = i.status !== "pago" && canRegisterPayment && loan.status !== "quitado";
        const canPayInterestOnly = canPay && i.late_fee_remaining > 0;
        return `
        <tr>
          <td>${i.number}</td>
          <td>${formatDate(i.due_date)}</td>
          <td>${formatMoney(i.base_amount)}</td>
          <td>${i.late_fee_accrued > 0 ? formatMoney(i.late_fee_accrued) : "-"}</td>
          <td>${formatMoney(i.paid_amount)}</td>
          <td><span class="status-pill status-${i.status}">${statusLabel(i.status)}</span></td>
          <td class="text-right">
            <div class="flex gap-1" style="justify-content:flex-end;flex-wrap:wrap;">
              ${canPayInterestOnly ? `<button class="btn btn-sm btn-outline pay-interest-btn" data-id="${i.id}" data-amount="${i.late_fee_remaining.toFixed(2)}">Pagar só os juros</button>` : ""}
              ${canPay ? `<button class="btn btn-sm btn-primary pay-btn" data-id="${i.id}" data-due="${Math.max(due, 0).toFixed(2)}">Registrar pagamento</button>` : ""}
            </div>
          </td>
        </tr>`;
      })
      .join("");

    document.querySelectorAll(".pay-btn").forEach((btn) =>
      btn.addEventListener("click", () => openPayModal(btn.dataset.id, btn.dataset.due))
    );
    document.querySelectorAll(".pay-interest-btn").forEach((btn) =>
      btn.addEventListener("click", () =>
        openPayModal(btn.dataset.id, btn.dataset.amount, "Pagamento somente dos juros/multa de atraso (parcela continua em aberto)")
      )
    );
  }

  function renderPayments() {
    const body = document.getElementById("paymentsBody");
    if (loan.payments.length === 0) {
      body.innerHTML = `<tr><td colspan="4" class="empty-state">Nenhum pagamento registrado ainda</td></tr>`;
      return;
    }
    body.innerHTML = [...loan.payments]
      .sort((a, b) => new Date(b.payment_date) - new Date(a.payment_date))
      .map(
        (p) => `
      <tr>
        <td>${formatDate(p.payment_date)}</td>
        <td>${formatMoney(p.amount)}</td>
        <td>${p.late_fee_included > 0 ? formatMoney(p.late_fee_included) : "-"}</td>
        <td>${escapeHtml(p.notes || "-")}</td>
      </tr>`
      )
      .join("");
  }

  // ---------- Payment modal ----------
  const payModal = document.getElementById("payModalBackdrop");
  function openPayModal(installmentId, due, defaultNotes) {
    document.getElementById("payInstallmentId").value = installmentId;
    document.getElementById("payAmount").value = due;
    document.getElementById("payDate").value = "";
    document.getElementById("payNotes").value = defaultNotes || "";
    document.getElementById("payFormError").classList.add("hidden");
    payModal.classList.remove("hidden");
  }
  document.getElementById("closePayModal").addEventListener("click", () => payModal.classList.add("hidden"));
  document.getElementById("cancelPayModal").addEventListener("click", () => payModal.classList.add("hidden"));
  document.getElementById("payForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const errBox = document.getElementById("payFormError");
    try {
      await api.post(`/loans/${loanId}/payments`, {
        installment_id: parseInt(document.getElementById("payInstallmentId").value),
        amount: parseFloat(document.getElementById("payAmount").value),
        payment_date: document.getElementById("payDate").value || null,
        notes: document.getElementById("payNotes").value || null,
      });
      payModal.classList.add("hidden");
      loadLoan();
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.remove("hidden");
    }
  });

  // ---------- Edit loan modal ----------
  const editModal = document.getElementById("editLoanModalBackdrop");
  function openEditLoanModal() {
    document.getElementById("editInterestRate").value = loan.interest_rate;
    document.getElementById("editLateFee").value = loan.late_fee_per_day;
    document.getElementById("editLoanFormError").classList.add("hidden");
    editModal.classList.remove("hidden");
  }
  document.getElementById("closeEditLoanModal").addEventListener("click", () => editModal.classList.add("hidden"));
  document.getElementById("cancelEditLoanModal").addEventListener("click", () => editModal.classList.add("hidden"));
  document.getElementById("editLoanForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const errBox = document.getElementById("editLoanFormError");
    try {
      await api.put(`/loans/${loanId}`, {
        interest_rate: parseFloat(document.getElementById("editInterestRate").value),
        late_fee_per_day: parseFloat(document.getElementById("editLateFee").value),
      });
      editModal.classList.add("hidden");
      loadLoan();
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.remove("hidden");
    }
  });

  // ---------- Payoff (quitação antecipada) modal ----------
  const payoffModal = document.getElementById("payoffModalBackdrop");
  async function openPayoffModal() {
    document.getElementById("payoffFormError").classList.add("hidden");
    document.getElementById("payoffDate").value = "";
    document.getElementById("payoffNotes").value = "";
    try {
      const suggestion = await api.get(`/loans/${loanId}/payoff-suggestion`);
      document.getElementById("payoffAmount").value = suggestion.suggested_amount;
      document.getElementById("payoffSuggestionHint").textContent =
        `Sugestão calculada pelo sistema: ${formatMoney(suggestion.suggested_amount)}. Você pode ajustar o valor final.`;
    } catch (e) {
      document.getElementById("payoffAmount").value = "";
    }
    payoffModal.classList.remove("hidden");
  }
  document.getElementById("closePayoffModal").addEventListener("click", () => payoffModal.classList.add("hidden"));
  document.getElementById("cancelPayoffModal").addEventListener("click", () => payoffModal.classList.add("hidden"));
  document.getElementById("payoffForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const errBox = document.getElementById("payoffFormError");
    try {
      await api.post(`/loans/${loanId}/baixar`, {
        payoff_amount: parseFloat(document.getElementById("payoffAmount").value),
        payment_date: document.getElementById("payoffDate").value || null,
        notes: document.getElementById("payoffNotes").value || null,
      });
      payoffModal.classList.add("hidden");
      loadLoan();
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.remove("hidden");
    }
  });

  loadLoan();
})();
