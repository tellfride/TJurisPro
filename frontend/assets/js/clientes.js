(async function () {
  const user = requireAuth(["administrador", "gestor", "operador"]);
  if (!user) return;
  renderShell("clientes.html");

  const canEdit = user.role === "administrador" || user.role === "gestor";
  const canCreate = user.role === "gestor" || user.role === "operador";

  let companyFilter = "";
  let searchTimer = null;

  if (canCreate) document.getElementById("newClientBtn").style.display = "inline-flex";

  if (user.role === "administrador") {
    const select = document.getElementById("companyFilter");
    select.style.display = "inline-block";
    try {
      const companies = await api.get("/companies");
      select.innerHTML =
        '<option value="">Selecione uma empresa</option>' +
        companies.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
    } catch (e) {}
    select.addEventListener("change", () => {
      companyFilter = select.value;
      loadClients();
    });
  }

  async function loadClients() {
    const body = document.getElementById("clientsBody");
    if (user.role === "administrador" && !companyFilter) {
      body.innerHTML = `<tr><td colspan="5" class="empty-state">Selecione uma empresa para ver os clientes</td></tr>`;
      return;
    }
    const params = new URLSearchParams();
    if (companyFilter) params.set("company_id", companyFilter);
    const search = document.getElementById("searchInput").value.trim();
    if (search) params.set("search", search);

    let clients;
    try {
      clients = await api.get(`/clients?${params.toString()}`);
    } catch (e) {
      body.innerHTML = `<tr><td colspan="5" class="empty-state">Erro ao carregar clientes</td></tr>`;
      return;
    }

    if (clients.length === 0) {
      body.innerHTML = `<tr><td colspan="5" class="empty-state">Nenhum cliente cadastrado</td></tr>`;
      return;
    }

    body.innerHTML = clients
      .map(
        (c) => `
      <tr>
        <td>${escapeHtml(c.name)}</td>
        <td>${escapeHtml(c.document || "-")}</td>
        <td>${escapeHtml(c.phone || "-")}</td>
        <td>${new Date(c.created_at).toLocaleDateString("pt-BR")}</td>
        <td class="text-right">
          <a class="btn btn-sm btn-outline" href="/emprestimos.html?client_id=${c.id}&client_name=${encodeURIComponent(c.name)}">Empréstimos</a>
          ${canEdit ? `<button class="btn btn-sm btn-outline edit-btn" data-id="${c.id}">Editar</button>` : ""}
        </td>
      </tr>`
      )
      .join("");

    document.querySelectorAll(".edit-btn").forEach((btn) => {
      btn.addEventListener("click", () => openEditModal(clients.find((c) => c.id === parseInt(btn.dataset.id))));
    });
  }

  document.getElementById("searchInput").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadClients, 300);
  });

  const modalBackdrop = document.getElementById("clientModalBackdrop");
  const form = document.getElementById("clientForm");
  const formError = document.getElementById("clientFormError");

  function openCreateModal() {
    document.getElementById("clientModalTitle").textContent = "Novo cliente";
    form.reset();
    document.getElementById("clientId").value = "";
    document.getElementById("clientCepHint").textContent = "";
    document.getElementById("clientDocumentHint").textContent = "";
    formError.classList.add("hidden");
    modalBackdrop.classList.remove("hidden");
  }

  function openEditModal(client) {
    if (!client) return;
    document.getElementById("clientModalTitle").textContent = "Editar cliente";
    document.getElementById("clientId").value = client.id;
    document.getElementById("clientName").value = client.name || "";
    document.getElementById("clientDocument").value = client.document || "";
    document.getElementById("clientPhone").value = client.phone || "";
    document.getElementById("clientEmail").value = client.email || "";
    document.getElementById("clientCep").value = client.cep || "";
    document.getElementById("clientAddress").value = client.address || "";
    document.getElementById("clientAddressNumber").value = client.address_number || "";
    document.getElementById("clientNotes").value = client.notes || "";
    document.getElementById("ref1Name").value = client.reference1_name || "";
    document.getElementById("ref1Phone").value = client.reference1_phone || "";
    document.getElementById("ref2Name").value = client.reference2_name || "";
    document.getElementById("ref2Phone").value = client.reference2_phone || "";
    document.getElementById("ref3Name").value = client.reference3_name || "";
    document.getElementById("ref3Phone").value = client.reference3_phone || "";
    document.getElementById("clientCepHint").textContent = "";
    document.getElementById("clientDocumentHint").textContent = "";
    formError.classList.add("hidden");
    modalBackdrop.classList.remove("hidden");
  }

  function closeModal() {
    modalBackdrop.classList.add("hidden");
  }

  document.getElementById("newClientBtn").addEventListener("click", openCreateModal);
  document.getElementById("closeClientModal").addEventListener("click", closeModal);
  document.getElementById("cancelClientModal").addEventListener("click", closeModal);
  wireCepAutofill("clientCep", "clientAddress", "clientCepHint");
  wireCpfValidation("clientDocument", "clientDocumentHint");

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const id = document.getElementById("clientId").value;
    const payload = {
      name: document.getElementById("clientName").value.trim(),
      document: document.getElementById("clientDocument").value.trim(),
      phone: document.getElementById("clientPhone").value.trim() || null,
      email: document.getElementById("clientEmail").value.trim() || null,
      cep: document.getElementById("clientCep").value.trim() || null,
      address: document.getElementById("clientAddress").value.trim() || null,
      address_number: document.getElementById("clientAddressNumber").value.trim() || null,
      notes: document.getElementById("clientNotes").value.trim() || null,
      reference1_name: document.getElementById("ref1Name").value.trim() || null,
      reference1_phone: document.getElementById("ref1Phone").value.trim() || null,
      reference2_name: document.getElementById("ref2Name").value.trim() || null,
      reference2_phone: document.getElementById("ref2Phone").value.trim() || null,
      reference3_name: document.getElementById("ref3Name").value.trim() || null,
      reference3_phone: document.getElementById("ref3Phone").value.trim() || null,
    };
    const saveBtn = document.getElementById("saveClientBtn");
    saveBtn.disabled = true;
    try {
      if (id) {
        await api.put(`/clients/${id}`, payload);
      } else {
        await api.post("/clients", payload);
      }
      closeModal();
      loadClients();
    } catch (err) {
      formError.textContent = err.message;
      formError.classList.remove("hidden");
    } finally {
      saveBtn.disabled = false;
    }
  });

  loadClients();
})();
