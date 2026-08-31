const NAV_ITEMS = [
  { href: "dashboard.html", label: "Dashboard", icon: "📊", roles: ["administrador", "gestor"] },
  { href: "clientes.html", label: "Clientes", icon: "👤", roles: ["administrador", "gestor", "operador"] },
  { href: "emprestimos.html", label: "Empréstimos", icon: "💰", roles: ["administrador", "gestor", "operador"] },
  { href: "relatorios.html", label: "Relatórios", icon: "📈", roles: ["administrador", "gestor"] },
  { href: "auditoria.html", label: "Auditoria", icon: "🛡️", roles: ["administrador", "gestor"] },
  { href: "configuracoes.html", label: "Configurações", icon: "⚙️", roles: ["administrador", "gestor"] },
  { href: "admin.html", label: "Administração", icon: "🏢", roles: ["administrador"] },
];

const ROLE_LABELS = { administrador: "Administrador", gestor: "Gestor", operador: "Operador" };

function initTheme() {
  const saved = localStorage.getItem("jurispro_theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
  updateThemeIcon();
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const currentlyDark = current ? current === "dark" : prefersDark;
  const next = currentlyDark ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("jurispro_theme", next);
  updateThemeIcon();
}

function updateThemeIcon() {
  const btn = document.getElementById("themeToggle");
  if (!btn) return;
  const current = document.documentElement.getAttribute("data-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const currentlyDark = current ? current === "dark" : prefersDark;
  btn.textContent = currentlyDark ? "☀️" : "🌙";
}

function requireAuth(allowedRoles) {
  const token = getToken();
  const user = getUser();
  if (!token || !user) {
    window.location.href = "/index.html";
    return null;
  }
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    window.location.href = "/clientes.html";
    return null;
  }
  return user;
}

function logout() {
  clearSession();
  window.location.href = "/index.html";
}

function renderShell(activeHref) {
  const user = getUser();
  if (!user) return;

  const sidebarSlot = document.getElementById("sidebarSlot");
  const topbarSlot = document.getElementById("topbarSlot");
  if (!sidebarSlot || !topbarSlot) return;

  const links = NAV_ITEMS.filter((item) => item.roles.includes(user.role))
    .map(
      (item) =>
        `<a class="nav-link${item.href === activeHref ? " active" : ""}" href="/${item.href}">` +
        `<span>${item.icon}</span><span>${item.label}</span></a>`
    )
    .join("");

  sidebarSlot.innerHTML = `
    <div class="brand">
      <img src="/assets/img/logo.png" alt="JurisPRO" />
      <span>JurisPRO</span>
    </div>
    ${links}
    <div class="sidebar-footer">
      <button class="btn btn-outline btn-sm" id="logoutBtn">Sair</button>
    </div>
  `;

  const pageTitle = (NAV_ITEMS.find((i) => i.href === activeHref) || {}).label || "JurisPRO";
  topbarSlot.innerHTML = `
    <div class="flex gap-1" style="align-items:center;">
      <button class="mobile-nav-toggle" id="navToggle">☰</button>
      <h1>${pageTitle}</h1>
    </div>
    <div class="flex gap-2" style="align-items:center;">
      <div class="user-chip">
        <span class="badge badge-${user.role === "administrador" ? "admin" : user.role}">${ROLE_LABELS[user.role]}</span>
        <span>${user.name}</span>
      </div>
      <button class="theme-toggle" id="themeToggle" title="Alternar tema">🌙</button>
    </div>
  `;

  let backdrop = document.getElementById("sidebarBackdrop");
  if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.id = "sidebarBackdrop";
    backdrop.className = "sidebar-backdrop";
    document.body.appendChild(backdrop);
  }

  function setSidebarOpen(open) {
    sidebarSlot.classList.toggle("open", open);
    backdrop.classList.toggle("open", open);
  }

  document.getElementById("logoutBtn").addEventListener("click", logout);
  document.getElementById("themeToggle").addEventListener("click", toggleTheme);
  document.getElementById("navToggle").addEventListener("click", () => {
    setSidebarOpen(!sidebarSlot.classList.contains("open"));
  });
  backdrop.addEventListener("click", () => setSidebarOpen(false));
  updateThemeIcon();
}

// Define o texto de uma dica e marca em vermelho quando é erro/aviso (ex:
// "CPF inválido", "CEP não encontrado"). Textos neutros (loading, vazio)
// ficam na cor padrão do .hint.
function setHint(element, text, isDanger) {
  if (!element) return;
  element.textContent = text || "";
  element.classList.toggle("hint-danger", Boolean(isDanger && text));
}

// Validação de CPF por dígito verificador (algoritmo oficial, módulo 11) —
// só confere o número matematicamente, não consulta nenhum serviço externo.
// Mesma lógica usada no backend (services/cpf_validator.py); aqui é só pra
// dar feedback instantâneo no formulário antes de enviar.
function isValidCpf(value) {
  const digits = (value || "").replace(/\D/g, "");
  if (digits.length !== 11) return false;
  if (new Set(digits.split("")).size === 1) return false;

  function checkDigit(base) {
    let total = 0;
    let weight = base.length + 1;
    for (const digit of base) {
      total += parseInt(digit, 10) * weight;
      weight -= 1;
    }
    const remainder = total % 11;
    return remainder < 2 ? 0 : 11 - remainder;
  }

  const digit1 = checkDigit(digits.slice(0, 9));
  const digit2 = checkDigit(digits.slice(0, 9) + String(digit1));
  return digits.slice(9, 11) === `${digit1}${digit2}`;
}

// Liga um input de CPF a um elemento de dica: ao sair do campo, mostra um
// aviso se o CPF não for válido (não bloqueia — a validação que decide é a
// do backend no envio do formulário).
function wireCpfValidation(cpfInputId, hintElementId) {
  const cpfInput = document.getElementById(cpfInputId);
  const hint = document.getElementById(hintElementId);
  if (!cpfInput || !hint) return;
  cpfInput.addEventListener("blur", () => {
    const value = cpfInput.value.trim();
    if (!value) {
      setHint(hint, "", false);
    } else if (!isValidCpf(value)) {
      setHint(hint, "CPF inválido — confira os números digitados.", true);
    } else {
      setHint(hint, "", false);
    }
  });
  cpfInput.addEventListener("input", () => {
    if (hint.textContent) setHint(hint, "", false);
  });
}

// Busca endereço pelo CEP via ViaCEP (API pública, sem chave, padrão pra isso
// no Brasil). Retorna { logradouro, bairro, localidade, uf } ou null se o
// CEP for inválido/não encontrado/a busca falhar (ex: sem internet).
async function lookupCep(cep) {
  const digits = (cep || "").replace(/\D/g, "");
  if (digits.length !== 8) return null;
  try {
    const response = await fetch(`https://viacep.com.br/ws/${digits}/json/`);
    const data = await response.json();
    if (data.erro) return null;
    return data;
  } catch (e) {
    return null;
  }
}

function formatCepAddress(data) {
  return [data.logradouro, data.bairro, data.localidade && data.uf ? `${data.localidade} - ${data.uf}` : data.localidade]
    .filter(Boolean)
    .join(", ");
}

// Liga um input de CEP a um input de endereço: ao sair do campo (ou ao digitar
// os 8 dígitos), busca e preenche o endereço automaticamente. O endereço
// continua editável manualmente depois.
function wireCepAutofill(cepInputId, addressInputId, hintElementId) {
  const cepInput = document.getElementById(cepInputId);
  const addressInput = document.getElementById(addressInputId);
  const hint = hintElementId ? document.getElementById(hintElementId) : null;
  if (!cepInput || !addressInput) return;

  async function runLookup() {
    const digits = cepInput.value.replace(/\D/g, "");
    if (digits.length !== 8) return;
    setHint(hint, "Buscando endereço...", false);
    const data = await lookupCep(cepInput.value);
    if (data) {
      addressInput.value = formatCepAddress(data);
      setHint(hint, "", false);
    } else {
      setHint(hint, "CEP não encontrado — preencha o endereço manualmente.", true);
    }
  }

  cepInput.addEventListener("blur", runLookup);
  cepInput.addEventListener("input", () => {
    if (cepInput.value.replace(/\D/g, "").length === 8) runLookup();
  });
}

// Abre o WhatsApp Web (ou o app, no celular) com uma mensagem já digitada
// numa conversa com esse número — não manda sozinho, só deixa pronto pra
// quem estiver com o WhatsApp Web conectado revisar e apertar Enviar.
// Retorna false se o telefone não parecer válido (sem abrir nada).
function openWhatsApp(phone, message) {
  const digits = (phone || "").replace(/\D/g, "");
  if (digits.length < 10) return false;
  const withCountryCode = digits.length <= 11 ? `55${digits}` : digits;
  const url = `https://wa.me/${withCountryCode}?text=${encodeURIComponent(message)}`;
  window.open(url, "_blank", "noopener");
  return true;
}

// Monta um lembrete simples de vencimento de parcela (usado nas tabelas de
// "próximos vencimentos" do dashboard).
function buildDueSoonMessage(clientName, dueDateIso, amount) {
  return (
    `Olá, ${clientName}! Passando para lembrar que sua parcela no valor de ${formatMoney(amount)} ` +
    `vence em ${formatDate(dueDateIso)}. Qualquer dúvida, estamos à disposição!`
  );
}

// Monta uma mensagem de cobrança/lembrete a partir do estado atual do
// empréstimo (usado na tela de detalhe do empréstimo).
function buildLoanCollectionMessage(loan) {
  const greeting = `Olá, ${loan.client.name}! Aqui é da equipe responsável pelo seu empréstimo Nº ${loan.loan_number}.`;
  const nextInstallment = loan.installments.find((i) => i.status !== "pago");
  if (!nextInstallment) {
    return `${greeting} Passando para avisar que o empréstimo está totalmente quitado. Obrigado!`;
  }
  const due = Math.max(0, nextInstallment.base_amount + nextInstallment.late_fee_accrued - nextInstallment.paid_amount);
  const dueText = formatDate(nextInstallment.due_date);
  if (nextInstallment.status === "atrasado") {
    return (
      `${greeting} Identificamos que a parcela ${nextInstallment.number} (vencimento ${dueText}) está em atraso, ` +
      `no valor de ${formatMoney(due)}. Poderia regularizar o pagamento? Qualquer dúvida, estamos à disposição.`
    );
  }
  return (
    `${greeting} Passando para lembrar que a parcela ${nextInstallment.number} vence em ${dueText}, ` +
    `no valor de ${formatMoney(due)}. Qualquer dúvida, estamos à disposição!`
  );
}

function formatMoney(value) {
  const n = typeof value === "number" ? value : parseFloat(value || 0);
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatDate(value) {
  if (!value) return "-";
  const [year, month, day] = value.split("-");
  return `${day}/${month}/${year}`;
}

function statusLabel(status) {
  const map = {
    ativo: "Ativo",
    atrasado: "Atrasado",
    quitado: "Quitado",
    pendente: "Pendente",
    pago: "Pago",
  };
  return map[status] || status;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

initTheme();
