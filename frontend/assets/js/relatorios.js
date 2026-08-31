(async function () {
  const user = requireAuth(["administrador", "gestor"]);
  if (!user) return;
  renderShell("relatorios.html");

  let companyId = "";

  if (user.role === "administrador") {
    document.getElementById("companyFieldWrap").style.display = "block";
    const select = document.getElementById("companySelect");
    try {
      const companies = await api.get("/companies");
      select.innerHTML =
        '<option value="">Todas as empresas</option>' +
        companies.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
    } catch (e) {}
    select.addEventListener("change", () => {
      companyId = select.value;
    });
  }

  // suporta abrir a página já filtrada por empresa (vindo de um card clicável do dashboard)
  const params = new URLSearchParams(window.location.search);
  if (params.get("company_id")) {
    companyId = params.get("company_id");
    const select = document.getElementById("companySelect");
    if (select) select.value = companyId;
  }

  document.getElementById("exportBtn").addEventListener("click", async () => {
    const errBox = document.getElementById("exportError");
    errBox.classList.add("hidden");
    const btn = document.getElementById("exportBtn");
    btn.disabled = true;
    btn.textContent = "Gerando...";
    try {
      const query = new URLSearchParams();
      if (companyId) query.set("company_id", companyId);
      const dateFrom = document.getElementById("dateFrom").value;
      if (dateFrom) query.set("date_from", dateFrom);
      const dateTo = document.getElementById("dateTo").value;
      if (dateTo) query.set("date_to", dateTo);
      await downloadFile(`/reports/transactions.xlsx?${query.toString()}`, "jurispro_transacoes.xlsx");
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.remove("hidden");
    } finally {
      btn.disabled = false;
      btn.textContent = "⬇ Baixar histórico (.xlsx)";
    }
  });
})();
