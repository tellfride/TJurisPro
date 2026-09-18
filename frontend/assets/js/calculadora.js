(function () {
  const user = requireAuth(["administrador", "gestor", "consultor"]);
  if (!user) return;
  renderShell("calculadora.html");

  // Mesma lógica de arredondamento e geração de parcelas do backend
  // (backend/app/services/interest_engine.py) — a simulação aqui bate
  // exatamente com o que o sistema gera de verdade ao lançar um empréstimo.
  function money(value) {
    return Math.round((value + Number.EPSILON) * 100) / 100;
  }

  function addMonths(base, months) {
    const year = base.getFullYear();
    const month = base.getMonth();
    const day = base.getDate();
    const index = month + months;
    const newYear = year + Math.floor(index / 12);
    const newMonth = ((index % 12) + 12) % 12;
    const daysInMonth = new Date(newYear, newMonth + 1, 0).getDate();
    return new Date(newYear, newMonth, Math.min(day, daysInMonth));
  }

  function parseDateInput(value) {
    if (!value) return new Date();
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day);
  }

  function formatDateObj(d) {
    return d.toLocaleDateString("pt-BR");
  }

  // ---------- Simulador de empréstimo ----------
  function updateLoanSimulation() {
    const principal = parseFloat(document.getElementById("calcPrincipal").value) || 0;
    const rate = parseFloat(document.getElementById("calcRate").value) || 0;
    const term = parseInt(document.getElementById("calcTerm").value) || 0;
    const startDate = parseDateInput(document.getElementById("calcStartDate").value);

    const totalEl = document.getElementById("calcLoanTotal");
    const profitEl = document.getElementById("calcLoanProfit");
    const body = document.getElementById("calcInstallmentsBody");

    if (principal <= 0 || term <= 0) {
      totalEl.textContent = "—";
      profitEl.textContent = "—";
      body.innerHTML = `<tr><td colspan="3" class="empty-state">Informe valor e prazo</td></tr>`;
      return;
    }

    const total = money(principal * (1 + rate / 100));
    totalEl.textContent = formatMoney(total);
    profitEl.textContent = formatMoney(money(total - principal));

    const base = money(total / term);
    let running = 0;
    const rows = [];
    for (let i = 1; i <= term; i++) {
      let amount = base;
      if (i === term) amount = money(total - running);
      running += amount;
      rows.push(`<tr><td>${i}/${term}</td><td>${formatDateObj(addMonths(startDate, i))}</td><td>${formatMoney(amount)}</td></tr>`);
    }
    body.innerHTML = rows.join("");
  }

  ["calcPrincipal", "calcRate", "calcTerm", "calcStartDate"].forEach((id) =>
    document.getElementById(id).addEventListener("input", updateLoanSimulation)
  );

  // ---------- Calculadora de multa por atraso ----------
  function updateFeeCalculation() {
    const installmentValue = parseFloat(document.getElementById("calcInstallmentValue").value) || 0;
    const feePerDay = parseFloat(document.getElementById("calcFeePerDay").value) || 0;
    const daysLate = Math.max(0, parseInt(document.getElementById("calcDaysLate").value) || 0);

    const fee = money(feePerDay * daysLate);
    document.getElementById("calcFeeTotal").textContent = formatMoney(fee);
    document.getElementById("calcFeeGrandTotal").textContent = formatMoney(money(installmentValue + fee));
  }

  document.getElementById("calcDueDate").addEventListener("input", () => {
    const value = document.getElementById("calcDueDate").value;
    if (!value) return;
    const due = parseDateInput(value);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    due.setHours(0, 0, 0, 0);
    const days = Math.round((today - due) / 86400000);
    document.getElementById("calcDaysLate").value = Math.max(0, days);
    updateFeeCalculation();
  });

  ["calcInstallmentValue", "calcFeePerDay", "calcDaysLate"].forEach((id) =>
    document.getElementById(id).addEventListener("input", updateFeeCalculation)
  );

  updateLoanSimulation();
  updateFeeCalculation();
})();
