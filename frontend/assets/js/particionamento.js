(async function () {
  const user = requireAuth(["gestor"]);
  if (!user) return;
  renderShell("particionamento.html");

  async function loadConsultants() {
    const body = document.getElementById("consultantsBody");
    let rows;
    try {
      rows = await api.get("/users?role=consultor");
    } catch (e) {
      body.innerHTML = `<tr><td colspan="4" class="empty-state">Erro ao carregar consultores</td></tr>`;
      return;
    }
    if (rows.length === 0) {
      body.innerHTML = `<tr><td colspan="4" class="empty-state">Nenhum consultor cadastrado</td></tr>`;
      return;
    }
    body.innerHTML = rows
      .map(
        (u) => `
      <tr>
        <td>${escapeHtml(u.name)}</td>
        <td>${escapeHtml(u.email)}</td>
        <td><span class="status-pill status-${u.active ? "quitado" : "atrasado"}">${u.active ? "Ativo" : "Bloqueado"}</span></td>
        <td class="text-right">
          <button class="btn btn-sm btn-outline perm-btn" data-id="${u.id}">Permissões</button>
          <button class="btn btn-sm btn-outline pwd-btn" data-id="${u.id}">Trocar senha</button>
          <button class="btn btn-sm btn-outline toggle-btn" data-id="${u.id}" data-active="${u.active}">${u.active ? "Bloquear" : "Ativar"}</button>
        </td>
      </tr>`
      )
      .join("");

    body.querySelectorAll(".toggle-btn").forEach((btn) =>
      btn.addEventListener("click", async () => {
        const active = btn.dataset.active === "true";
        await api.put(`/users/${btn.dataset.id}`, { active: !active });
        loadConsultants();
      })
    );
    body.querySelectorAll(".pwd-btn").forEach((btn) =>
      btn.addEventListener("click", () => {
        const target = rows.find((u) => String(u.id) === btn.dataset.id);
        openChangePasswordModal(target);
      })
    );
    body.querySelectorAll(".perm-btn").forEach((btn) =>
      btn.addEventListener("click", () => {
        const target = rows.find((u) => String(u.id) === btn.dataset.id);
        openConsultantPermissionsModal(target);
      })
    );
  }

  // ---------- Modal de novo consultor ----------
  const teamModal = document.getElementById("teamModalBackdrop");
  const teamForm = document.getElementById("teamForm");
  const teamFormError = document.getElementById("teamFormError");

  document.getElementById("newConsultantBtn").addEventListener("click", () => {
    teamForm.reset();
    teamFormError.classList.add("hidden");
    teamModal.classList.remove("hidden");
  });
  document.getElementById("closeTeamModal").addEventListener("click", () => teamModal.classList.add("hidden"));
  document.getElementById("cancelTeamModal").addEventListener("click", () => teamModal.classList.add("hidden"));

  teamForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const payload = {
      name: document.getElementById("teamName").value.trim(),
      email: document.getElementById("teamEmail").value.trim(),
      password: document.getElementById("teamPassword").value,
      role: "consultor",
    };
    try {
      await api.post("/users", payload);
      teamModal.classList.add("hidden");
      loadConsultants();
    } catch (err) {
      teamFormError.textContent = err.message;
      teamFormError.classList.remove("hidden");
    }
  });

  loadConsultants();
})();
