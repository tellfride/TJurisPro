(async function () {
  const user = requireAuth(["administrador", "gestor"]);
  if (!user) return;
  renderShell("configuracoes.html");

  let companyId = user.company_id;

  if (user.role === "administrador") {
    document.getElementById("companyFieldWrap").style.display = "block";
    const select = document.getElementById("companySelect");
    try {
      const companies = await api.get("/companies");
      select.innerHTML = companies.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
      companyId = companies.length ? companies[0].id : null;
    } catch (e) {}
    select.addEventListener("change", () => {
      companyId = parseInt(select.value);
      loadSettings();
      loadTemplates();
    });
  }

  async function loadSettings() {
    if (!companyId) return;
    document.getElementById("settingsError").classList.add("hidden");
    document.getElementById("settingsSuccess").classList.add("hidden");
    try {
      const settings = await api.get(`/settings/notifications?company_id=${companyId}`);
      document.getElementById("botToken").value = settings.telegram_bot_token || "";
      document.getElementById("chatId").value = settings.telegram_chat_id || "";
      document.getElementById("notifyDays").value = settings.notify_days_before;
    } catch (e) {
      document.getElementById("settingsError").textContent = e.message;
      document.getElementById("settingsError").classList.remove("hidden");
    }
  }

  document.getElementById("settingsForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const errBox = document.getElementById("settingsError");
    const okBox = document.getElementById("settingsSuccess");
    errBox.classList.add("hidden");
    okBox.classList.add("hidden");
    try {
      await api.put(`/settings/notifications?company_id=${companyId}`, {
        telegram_bot_token: document.getElementById("botToken").value.trim() || null,
        telegram_chat_id: document.getElementById("chatId").value.trim() || null,
        notify_days_before: parseInt(document.getElementById("notifyDays").value),
      });
      okBox.textContent = "Configurações salvas com sucesso.";
      okBox.classList.remove("hidden");
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.remove("hidden");
    }
  });

  loadSettings();

  // ---------- Modelos de mensagem WhatsApp ----------
  let templates = [];

  async function loadTemplates() {
    const body = document.getElementById("templatesBody");
    if (!companyId) return;
    try {
      templates = await api.get(`/whatsapp-templates?company_id=${companyId}`);
    } catch (e) {
      body.innerHTML = `<tr><td colspan="3" class="empty-state">Erro ao carregar modelos</td></tr>`;
      return;
    }
    if (templates.length === 0) {
      body.innerHTML = `<tr><td colspan="3" class="empty-state">Nenhum modelo cadastrado</td></tr>`;
      return;
    }
    body.innerHTML = templates
      .map(
        (t) => `
      <tr>
        <td>${escapeHtml(t.name)}</td>
        <td class="text-muted" style="font-size:0.82rem;max-width:320px;">${escapeHtml(t.content.slice(0, 90))}${t.content.length > 90 ? "…" : ""}</td>
        <td class="text-right">
          <button class="btn btn-sm btn-outline edit-template" data-id="${t.id}">Editar</button>
          <button class="btn btn-sm btn-outline btn-danger delete-template" data-id="${t.id}">Excluir</button>
        </td>
      </tr>`
      )
      .join("");

    document.querySelectorAll(".edit-template").forEach((btn) =>
      btn.addEventListener("click", () => openTemplateModal(templates.find((t) => t.id === parseInt(btn.dataset.id))))
    );
    document.querySelectorAll(".delete-template").forEach((btn) =>
      btn.addEventListener("click", async () => {
        if (!confirm("Excluir este modelo de mensagem?")) return;
        await api.delete(`/whatsapp-templates/${btn.dataset.id}`);
        loadTemplates();
      })
    );
  }

  const templateModal = document.getElementById("templateModalBackdrop");
  const templateForm = document.getElementById("templateForm");
  const templateFormError = document.getElementById("templateFormError");

  function openTemplateModal(template) {
    document.getElementById("templateModalTitle").textContent = template ? "Editar modelo" : "Novo modelo";
    document.getElementById("templateId").value = template ? template.id : "";
    document.getElementById("templateName").value = template ? template.name : "";
    document.getElementById("templateContent").value = template ? template.content : "";
    templateFormError.classList.add("hidden");
    templateModal.classList.remove("hidden");
  }

  document.getElementById("newTemplateBtn").addEventListener("click", () => openTemplateModal(null));
  document.getElementById("closeTemplateModal").addEventListener("click", () => templateModal.classList.add("hidden"));
  document.getElementById("cancelTemplateModal").addEventListener("click", () => templateModal.classList.add("hidden"));

  templateForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const id = document.getElementById("templateId").value;
    const payload = {
      name: document.getElementById("templateName").value.trim(),
      content: document.getElementById("templateContent").value.trim(),
    };
    try {
      if (id) {
        await api.put(`/whatsapp-templates/${id}`, payload);
      } else {
        await api.post(`/whatsapp-templates?company_id=${companyId}`, payload);
      }
      templateModal.classList.add("hidden");
      loadTemplates();
    } catch (err) {
      templateFormError.textContent = err.message;
      templateFormError.classList.remove("hidden");
    }
  });

  loadTemplates();
})();
