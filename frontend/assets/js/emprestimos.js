(async function () {
  const user = requireAuth(["administrador", "gestor", "consultor"]);
  if (!user) return;
  renderShell("emprestimos.html");

  const canCreate = user.role === "gestor" || (user.role === "consultor" && consultorPerm(user, "register_loans"));
  const canSendWhatsapp = consultorPerm(user, "send_whatsapp");
  const params = new URLSearchParams(window.location.search);
  const clientId = params.get("client_id");
  const clientName = params.get("client_name");

  let companyFilter = "";
  let clientsById = {};

  if (clientId) {
    document.getElementById("filterBanner").style.display = "flex";
    document.getElementById("filterBannerText").textContent = `Empréstimos de ${clientName || "cliente #" + clientId}`;
  }

  const statusParam = params.get("status");
  if (statusParam) document.getElementById("statusFilter").value = statusParam;

  if (canCreate) {
    document.getElementById("newLoanBtn").style.display = "inline-flex";
    document.getElementById("importBtn").style.display = "inline-flex";
  }

  if (user.role === "administrador") {
    const select = document.getElementById("companyFilter");
    select.style.display = "inline-block";
    try {
      const companies = await api.get("/companies");
      select.innerHTML =
        '<option value="">Selecione uma empresa</option>' +
        companies.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
    } catch (e) {}
    const companyParam = params.get("company_id");
    if (companyParam) {
      select.value = companyParam;
      companyFilter = companyParam;
    }
    select.addEventListener("change", () => {
      companyFilter = select.value;
      loadLoans();
    });
  }

  document.getElementById("statusFilter").addEventListener("change", loadLoans);

  async function loadLoans() {
    const body = document.getElementById("loansBody");
    if (user.role === "administrador" && !companyFilter && !clientId) {
      body.innerHTML = `<tr><td colspan="8" class="empty-state">Selecione uma empresa para ver os empréstimos</td></tr>`;
      return;
    }
    const query = new URLSearchParams();
    if (companyFilter) query.set("company_id", companyFilter);
    if (clientId) query.set("client_id", clientId);
    const status = document.getElementById("statusFilter").value;
    if (status) query.set("status", status);

    let loans;
    try {
      loans = await api.get(`/loans?${query.toString()}`);
    } catch (e) {
      body.innerHTML = `<tr><td colspan="8" class="empty-state">Erro ao carregar empréstimos</td></tr>`;
      return;
    }

    if (loans.length === 0) {
      body.innerHTML = `<tr><td colspan="8" class="empty-state">Nenhum empréstimo encontrado</td></tr>`;
      return;
    }

    const rows = await Promise.all(
      loans.map(async (l) => {
        const clientNameCell = clientsById[l.client_id] || (await fetchClientName(l.client_id));
        return `
        <tr>
          <td>${l.loan_number}</td>
          <td>${escapeHtml(clientNameCell)}</td>
          <td>${formatMoney(l.principal)}</td>
          <td>${Number(l.interest_rate).toFixed(2)}%</td>
          <td>${l.term_months}x</td>
          <td>${formatMoney(l.total_amount)}</td>
          <td><span class="status-pill status-${l.status}">${statusLabel(l.status)}</span></td>
          <td class="text-right">
            <div class="flex gap-1" style="justify-content:flex-end;">
              ${canSendWhatsapp && l.status !== "quitado" ? `<button class="btn btn-sm btn-whatsapp collect-btn" data-loan-id="${l.id}">💬 Cobrar via WhatsApp</button>` : ""}
              <a class="btn btn-sm btn-outline" href="/emprestimo_detalhe.html?id=${l.id}">Detalhes</a>
            </div>
          </td>
        </tr>`;
      })
    );
    body.innerHTML = rows.join("");

    // A lista não traz telefone nem parcelas: busca o detalhe do empréstimo na hora
    // do clique e abre o mesmo compositor da página do empréstimo.
    body.querySelectorAll(".collect-btn").forEach((btn) =>
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        try {
          const loan = await api.get(`/loans/${btn.dataset.loanId}`);
          await openLoanCollectionComposer(loan);
        } catch (e) {
          alert(e.message || "Não foi possível abrir a cobrança.");
        } finally {
          btn.disabled = false;
        }
      })
    );
  }

  async function fetchClientName(id) {
    try {
      const client = await api.get(`/clients/${id}`);
      clientsById[id] = client.name;
      return client.name;
    } catch (e) {
      return `Cliente #${id}`;
    }
  }

  async function loadClientOptions() {
    if (!canCreate) return;
    try {
      const clients = await api.get("/clients");
      clientsById = {};
      const datalist = document.getElementById("clientsDatalist");
      datalist.innerHTML = clients.map((c) => `<option value="${escapeHtml(c.name)}" data-id="${c.id}"></option>`).join("");
      clients.forEach((c) => (clientsById[c.id] = c.name));
    } catch (e) {}
  }

  const modalBackdrop = document.getElementById("loanModalBackdrop");
  const form = document.getElementById("loanForm");
  const formError = document.getElementById("loanFormError");

  function openLoanModal() {
    form.reset();
    formError.classList.add("hidden");
    document.getElementById("newClientFields").style.display = "none";
    if (clientId && clientName) {
      document.getElementById("clientPicker").value = clientName;
      document.getElementById("clientPickerField").style.display = "none";
    } else {
      document.getElementById("clientPickerField").style.display = "block";
    }
    document.getElementById("loanPreview").textContent = "";
    modalBackdrop.classList.remove("hidden");
  }

  function isNewClientName() {
    if (clientId) return false;
    return !resolveClientId() && document.getElementById("clientPicker").value.trim().length > 0;
  }

  document.getElementById("clientPicker").addEventListener("input", () => {
    document.getElementById("newClientFields").style.display = isNewClientName() ? "block" : "none";
  });

  function closeLoanModal() {
    modalBackdrop.classList.add("hidden");
  }

  document.getElementById("newLoanBtn").addEventListener("click", async () => {
    await loadClientOptions();
    openLoanModal();
  });
  document.getElementById("closeLoanModal").addEventListener("click", closeLoanModal);
  document.getElementById("cancelLoanModal").addEventListener("click", closeLoanModal);
  wireCepAutofill("newClientCep", "newClientAddress", "newClientCepHint");
  wireCpfValidation("newClientDocument", "newClientDocumentHint");

  function updatePreview() {
    const principal = parseFloat(document.getElementById("principal").value) || 0;
    const rate = parseFloat(document.getElementById("interestRate").value) || 0;
    const term = parseInt(document.getElementById("termMonths").value) || 0;
    const preview = document.getElementById("loanPreview");
    if (principal > 0 && term > 0) {
      const total = principal * (1 + rate / 100);
      const installment = total / term;
      preview.textContent = `Total a pagar: ${formatMoney(total)} em ${term}x de ${formatMoney(installment)} (sem atraso)`;
    } else {
      preview.textContent = "";
    }
  }
  ["principal", "interestRate", "termMonths"].forEach((id) =>
    document.getElementById(id).addEventListener("input", updatePreview)
  );

  // Casa o texto digitado com um cliente já cadastrado (ignorando maiúsculas/
  // acentuação de caixa e espaços nas pontas). Se não achar, retorna null e o
  // submit trata como "cliente novo" e cadastra automaticamente.
  function resolveClientId() {
    if (clientId) return parseInt(clientId);
    const typed = document.getElementById("clientPicker").value.trim();
    if (!typed) return null;
    const lower = typed.toLowerCase();
    const match = Object.entries(clientsById).find(([, name]) => name.trim().toLowerCase() === lower);
    return match ? parseInt(match[0]) : null;
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    formError.classList.add("hidden");
    const saveBtn = document.getElementById("saveLoanBtn");
    saveBtn.disabled = true;
    try {
      let targetClientId = resolveClientId();
      if (!targetClientId) {
        const typedName = document.getElementById("clientPicker").value.trim();
        if (!typedName) {
          throw new Error("Informe o nome do cliente.");
        }
        const newDocument = document.getElementById("newClientDocument").value.trim();
        if (!newDocument) {
          throw new Error("Informe o CPF do cliente novo.");
        }
        // Nome não bate com nenhum cliente já cadastrado: cadastra um cliente
        // novo com esse nome antes de lançar o empréstimo.
        const newClient = await api.post("/clients", {
          name: typedName,
          document: newDocument,
          phone: document.getElementById("newClientPhone").value.trim() || null,
          cep: document.getElementById("newClientCep").value.trim() || null,
          address: document.getElementById("newClientAddress").value.trim() || null,
          address_number: document.getElementById("newClientAddressNumber").value.trim() || null,
          reference1_name: document.getElementById("newClientRef1Name").value.trim() || null,
          reference1_phone: document.getElementById("newClientRef1Phone").value.trim() || null,
          reference2_name: document.getElementById("newClientRef2Name").value.trim() || null,
          reference2_phone: document.getElementById("newClientRef2Phone").value.trim() || null,
          reference3_name: document.getElementById("newClientRef3Name").value.trim() || null,
          reference3_phone: document.getElementById("newClientRef3Phone").value.trim() || null,
        });
        clientsById[newClient.id] = newClient.name;
        targetClientId = newClient.id;
      }
      const payload = {
        client_id: targetClientId,
        principal: parseFloat(document.getElementById("principal").value),
        interest_rate: parseFloat(document.getElementById("interestRate").value),
        term_months: parseInt(document.getElementById("termMonths").value),
        late_fee_per_day: parseFloat(document.getElementById("lateFeePerDay").value),
        start_date: document.getElementById("startDate").value || null,
      };
      await api.post("/loans", payload);
      closeLoanModal();
      loadLoans();
    } catch (err) {
      formError.textContent = err.message;
      formError.classList.remove("hidden");
    } finally {
      saveBtn.disabled = false;
    }
  });

  // ---------- Importar planilha ----------
  const importModal = document.getElementById("importModalBackdrop");
  const importError = document.getElementById("importFormError");
  const importResult = document.getElementById("importResultBox");

  document.getElementById("importBtn").addEventListener("click", () => {
    document.getElementById("importFile").value = "";
    importError.classList.add("hidden");
    importResult.style.display = "none";
    importModal.classList.remove("hidden");
  });
  document.getElementById("closeImportModal").addEventListener("click", () => importModal.classList.add("hidden"));
  document.getElementById("cancelImportModal").addEventListener("click", () => importModal.classList.add("hidden"));

  document.getElementById("downloadTemplateLink").addEventListener("click", async (ev) => {
    ev.preventDefault();
    try {
      await downloadFile("/imports/clients-loans/template.xlsx", "jurispro_modelo_importacao.xlsx");
    } catch (err) {
      importError.textContent = err.message;
      importError.classList.remove("hidden");
    }
  });

  document.getElementById("submitImportBtn").addEventListener("click", async () => {
    const fileInput = document.getElementById("importFile");
    const file = fileInput.files[0];
    importError.classList.add("hidden");
    importResult.style.display = "none";
    if (!file) {
      importError.textContent = "Selecione um arquivo .xlsx primeiro.";
      importError.classList.remove("hidden");
      return;
    }
    const btn = document.getElementById("submitImportBtn");
    btn.disabled = true;
    btn.textContent = "Enviando...";
    try {
      const result = await uploadFile("/imports/clients-loans", file);
      let html = `${result.clients_created} cliente(s) e ${result.loans_created} empréstimo(s) importados com sucesso.`;
      if (result.errors.length > 0) {
        html += `<div class="hint-danger" style="margin-top:0.4rem;"><strong>${result.errors.length} linha(s) com erro:</strong><ul style="margin:0.3rem 0 0 1.1rem;padding:0;">`;
        html += result.errors.map((e) => `<li>Linha ${e.row}: ${escapeHtml(e.message)}</li>`).join("");
        html += "</ul></div>";
      }
      importResult.innerHTML = html;
      importResult.style.display = "block";
      loadLoans();
    } catch (err) {
      importError.textContent = err.message;
      importError.classList.remove("hidden");
    } finally {
      btn.disabled = false;
      btn.textContent = "Enviar planilha";
    }
  });

  loadLoans();
})();
