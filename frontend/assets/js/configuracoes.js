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
})();
