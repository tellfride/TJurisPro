(async function () {
  const user = requireAuth(["administrador"]);
  if (!user) return;
  renderShell("admin.html");

  let companies = [];

  async function loadCompanies() {
    try {
      companies = await api.get("/companies");
    } catch (e) {
      companies = [];
    }
    renderCompaniesTable();
    renderCompanyDropdowns();
  }

  function renderCompaniesTable() {
    const body = document.getElementById("companiesBody");
    if (companies.length === 0) {
      body.innerHTML = `<tr><td colspan="3" class="empty-state">Nenhuma empresa cadastrada</td></tr>`;
      return;
    }
    body.innerHTML = companies
      .map(
        (c) => `
      <tr>
        <td>${escapeHtml(c.name)}</td>
        <td><span class="status-pill status-${c.active ? "quitado" : "atrasado"}">${c.active ? "Ativa" : "Inativa"}</span></td>
        <td class="text-right"><button class="btn btn-sm btn-outline toggle-company" data-id="${c.id}" data-active="${c.active}">${c.active ? "Desativar" : "Ativar"}</button></td>
      </tr>`
      )
      .join("");

    document.querySelectorAll(".toggle-company").forEach((btn) =>
      btn.addEventListener("click", async () => {
        const active = btn.dataset.active === "true";
        await api.put(`/companies/${btn.dataset.id}`, { active: !active });
        loadCompanies();
      })
    );
  }

  function renderCompanyDropdowns() {
    const options = companies.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
    document.getElementById("usersCompanyFilter").innerHTML = options || '<option value="">Nenhuma empresa</option>';
    document.getElementById("userCompany").innerHTML = options;
    if (companies.length > 0) loadUsers();
  }

  async function loadUsers() {
    const companyId = document.getElementById("usersCompanyFilter").value;
    const body = document.getElementById("usersBody");
    if (!companyId) {
      body.innerHTML = `<tr><td colspan="5" class="empty-state">Cadastre uma empresa primeiro</td></tr>`;
      return;
    }
    let users;
    try {
      users = await api.get(`/users?company_id=${companyId}`);
    } catch (e) {
      body.innerHTML = `<tr><td colspan="5" class="empty-state">Erro ao carregar usuários</td></tr>`;
      return;
    }
    if (users.length === 0) {
      body.innerHTML = `<tr><td colspan="5" class="empty-state">Nenhum usuário nesta empresa</td></tr>`;
      return;
    }
    const roleLabels = { administrador: "Administrador", gestor: "Gestor", operador: "Operador" };
    body.innerHTML = users
      .map(
        (u) => `
      <tr>
        <td>${escapeHtml(u.name)}</td>
        <td>${escapeHtml(u.email)}</td>
        <td>${roleLabels[u.role]}</td>
        <td><span class="status-pill status-${u.active ? "quitado" : "atrasado"}">${u.active ? "Ativo" : "Inativo"}</span></td>
        <td class="text-right"><button class="btn btn-sm btn-outline toggle-user" data-id="${u.id}" data-active="${u.active}">${u.active ? "Desativar" : "Ativar"}</button></td>
      </tr>`
      )
      .join("");

    document.querySelectorAll(".toggle-user").forEach((btn) =>
      btn.addEventListener("click", async () => {
        const active = btn.dataset.active === "true";
        await api.put(`/users/${btn.dataset.id}`, { active: !active });
        loadUsers();
      })
    );
  }

  document.getElementById("usersCompanyFilter").addEventListener("change", loadUsers);

  // ---------- Company modal ----------
  const companyModal = document.getElementById("companyModalBackdrop");
  document.getElementById("newCompanyBtn").addEventListener("click", () => {
    document.getElementById("companyForm").reset();
    document.getElementById("companyFormError").classList.add("hidden");
    companyModal.classList.remove("hidden");
  });
  document.getElementById("closeCompanyModal").addEventListener("click", () => companyModal.classList.add("hidden"));
  document.getElementById("cancelCompanyModal").addEventListener("click", () => companyModal.classList.add("hidden"));
  document.getElementById("companyForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const errBox = document.getElementById("companyFormError");
    try {
      await api.post("/companies", { name: document.getElementById("companyName").value.trim() });
      companyModal.classList.add("hidden");
      loadCompanies();
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.remove("hidden");
    }
  });

  // ---------- User modal ----------
  const userModal = document.getElementById("userModalBackdrop");
  function toggleCompanyField() {
    const role = document.getElementById("userRole").value;
    document.getElementById("userCompanyField").style.display = role === "administrador" ? "none" : "block";
  }
  document.getElementById("userRole").addEventListener("change", toggleCompanyField);

  document.getElementById("newUserBtn").addEventListener("click", () => {
    document.getElementById("userForm").reset();
    document.getElementById("userFormError").classList.add("hidden");
    const preselected = document.getElementById("usersCompanyFilter").value;
    if (preselected) document.getElementById("userCompany").value = preselected;
    toggleCompanyField();
    userModal.classList.remove("hidden");
  });
  document.getElementById("closeUserModal").addEventListener("click", () => userModal.classList.add("hidden"));
  document.getElementById("cancelUserModal").addEventListener("click", () => userModal.classList.add("hidden"));
  document.getElementById("userForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const errBox = document.getElementById("userFormError");
    const role = document.getElementById("userRole").value;
    const payload = {
      name: document.getElementById("userName").value.trim(),
      email: document.getElementById("userEmail").value.trim(),
      password: document.getElementById("userPassword").value,
      role,
      company_id: role === "administrador" ? null : parseInt(document.getElementById("userCompany").value),
    };
    try {
      await api.post("/users", payload);
      userModal.classList.add("hidden");
      loadUsers();
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.remove("hidden");
    }
  });

  loadCompanies();
})();
