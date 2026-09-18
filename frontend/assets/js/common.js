const NAV_ITEMS = [
  { href: "dashboard.html", label: "Dashboard", icon: "📊", roles: ["administrador", "gestor", "consultor"], permission: "view_dashboard" },
  { href: "clientes.html", label: "Clientes", icon: "👤", roles: ["administrador", "gestor", "consultor"] },
  { href: "emprestimos.html", label: "Empréstimos", icon: "💰", roles: ["administrador", "gestor", "consultor"] },
  { href: "calculadora.html", label: "Calculadora", icon: "🧮", roles: ["administrador", "gestor", "consultor"] },
  { href: "relatorios.html", label: "Relatórios", icon: "📈", roles: ["administrador", "gestor", "consultor"], permission: "view_reports" },
  { href: "auditoria.html", label: "Auditoria", icon: "🛡️", roles: ["administrador", "gestor", "consultor"], permission: "view_audit" },
  { href: "particionamento.html", label: "Particionamento", icon: "🧩", roles: ["gestor"] },
  { href: "configuracoes.html", label: "Configurações", icon: "⚙️", roles: ["administrador", "gestor"] },
  { href: "admin.html", label: "Administração", icon: "🏢", roles: ["administrador"] },
];

const ROLE_LABELS = { administrador: "Administrador", gestor: "Gestor", operador: "Operador", consultor: "Consultor" };

// Para o papel Consultor, cada campo de ConsultantPermissions liga/desliga
// uma capacidade específica (ver [[particionamento]] — o gestor habilita na
// aba de Particionamento). Qualquer outro papel sempre retorna true aqui:
// suas permissões continuam fixas por papel, como sempre foram.
function consultorPerm(user, key) {
  if (!user || user.role !== "consultor") return true;
  return Boolean(user.permissions && user.permissions[key]);
}

function navAllowed(item, user) {
  if (!item.roles.includes(user.role)) return false;
  if (item.permission) return consultorPerm(user, item.permission);
  return true;
}

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

  const links = NAV_ITEMS.filter((item) => navAllowed(item, user))
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
        <span>${escapeHtml(user.name)}</span>
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

  renderAppFooter(document.querySelector(".main-area"));
  if (user.role !== "administrador") loadLicenseBanner();
}

// Rodapé padrão (versão + crédito do desenvolvedor). renderShell() chama isto
// nas páginas internas; o index.html (login) chama direto. Para mudar a versão
// mostrada, é só editar APP_VERSION.
const APP_VERSION = "1.0.1";
const APP_FOOTER_WHATSAPP_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/></svg>';

function renderAppFooter(parent) {
  if (!parent || parent.querySelector(".app-footer")) return;
  const footer = document.createElement("footer");
  footer.className = "app-footer";
  footer.innerHTML =
    `<span class="app-footer-version"><i></i>Versão ${APP_VERSION}</span>` +
    `<span class="app-footer-dev">Desenvolvido por <b>T-Labex Tecnologia</b></span>` +
    `<a class="app-footer-zap" href="https://wa.me/5521980155573" target="_blank" rel="noopener noreferrer">` +
    `${APP_FOOTER_WHATSAPP_ICON}21 98015-5573</a>`;
  parent.appendChild(footer);
}

// Busca o status da licença da empresa e, se estiver vencida ou vencendo em
// breve, injeta um aviso no topo do conteúdo da página (uma vez por
// carregamento — não fica reconsultando). Silenciosamente não faz nada se a
// chamada falhar (ex: sessão expirando bem nesse instante).
async function loadLicenseBanner() {
  const content = document.querySelector(".content");
  if (!content) return;
  let status;
  try {
    status = await api.get("/companies/license-status");
  } catch (e) {
    return;
  }
  if (!status || !status.license_expires_at) return;

  const expiresText = formatDate(status.license_expires_at.slice(0, 10));
  let banner = document.getElementById("licenseBanner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "licenseBanner";
    content.prepend(banner);
  }
  if (status.expired) {
    banner.className = "license-banner danger";
    banner.textContent = `🔒 A licença da sua empresa expirou em ${expiresText}. Fale com o administrador do sistema para renovar o plano.`;
  } else if (status.days_remaining !== null && status.days_remaining <= 7) {
    banner.className = "license-banner warning";
    banner.textContent = `⏳ A licença da sua empresa vence em ${expiresText} (${status.days_remaining} dia${status.days_remaining === 1 ? "" : "s"}). Fale com o administrador do sistema para renovar.`;
  } else {
    banner.remove();
  }
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

// Modelos de mensagem WhatsApp cadastrados pela empresa (Configurações) —
// buscados uma vez e reaproveitados pelo composer enquanto a página estiver
// aberta (evita recarregar a lista a cada clique em "💬").
let _whatsappTemplatesCache = null;
async function fetchWhatsappTemplates() {
  if (_whatsappTemplatesCache) return _whatsappTemplatesCache;
  try {
    _whatsappTemplatesCache = await api.get("/whatsapp-templates");
  } catch (e) {
    _whatsappTemplatesCache = [];
  }
  return _whatsappTemplatesCache;
}

// Substitui placeholders {{campo}} pelos valores em vars (ex: {{cliente}} ->
// "Maria Silva"). Placeholder sem valor correspondente é deixado como está.
function renderWhatsappTemplate(content, vars) {
  return (content || "").replace(/\{\{\s*(\w+)\s*\}\}/g, (match, key) => {
    const value = vars ? vars[key] : undefined;
    return value === undefined || value === null ? match : String(value);
  });
}

// Mostra um modal com a mensagem pré-preenchida (editável) antes de abrir o
// WhatsApp — permite escolher um modelo cadastrado pela empresa ou escrever
// à vontade antes de enviar. Cria o modal na primeira vez que é chamado e
// reaproveita depois. `templateVars` alimenta os placeholders {{...}} dos
// modelos (ex: {cliente, valor, vencimento, parcela, emprestimo, os}).
// `context` (opcional): { loanId, onLogged } — com loanId, ao abrir o WhatsApp a
// cobrança é registrada no histórico da OS (best-effort: se falhar, o WhatsApp
// abre do mesmo jeito); onLogged() roda depois do registro (ex.: recarregar).
async function openWhatsAppComposer(phone, defaultMessage, templateVars, context) {
  const digits = (phone || "").replace(/\D/g, "");
  if (digits.length < 10) {
    alert("Telefone do cliente inválido ou não cadastrado.");
    return;
  }
  const vars = templateVars || {};

  let backdrop = document.getElementById("whatsappComposerBackdrop");
  if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop hidden";
    backdrop.id = "whatsappComposerBackdrop";
    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h3>💬 Mensagem via WhatsApp</h3>
          <button class="icon-btn" id="closeWhatsappComposer" type="button">✕</button>
        </div>
        <div class="field" id="whatsappTemplateFieldWrap" style="display:none;">
          <label for="whatsappTemplateSelect">Modelo cadastrado</label>
          <select id="whatsappTemplateSelect">
            <option value="">Mensagem automática</option>
          </select>
        </div>
        <div class="field">
          <label for="whatsappComposerText">Mensagem (personalize à vontade)</label>
          <textarea id="whatsappComposerText" rows="6"></textarea>
        </div>
        <div class="form-actions">
          <button type="button" class="btn btn-outline" id="cancelWhatsappComposer">Cancelar</button>
          <button type="button" class="btn btn-primary" id="sendWhatsappComposer">Abrir WhatsApp</button>
        </div>
      </div>`;
    document.body.appendChild(backdrop);
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) backdrop.classList.add("hidden");
    });
    document.getElementById("closeWhatsappComposer").addEventListener("click", () => backdrop.classList.add("hidden"));
    document.getElementById("cancelWhatsappComposer").addEventListener("click", () => backdrop.classList.add("hidden"));
  }

  const textarea = document.getElementById("whatsappComposerText");
  const templateSelect = document.getElementById("whatsappTemplateSelect");
  const templateFieldWrap = document.getElementById("whatsappTemplateFieldWrap");

  textarea.value = defaultMessage;
  templateSelect.onchange = () => {
    const templates = templateSelect._templates || [];
    const template = templates.find((t) => String(t.id) === templateSelect.value);
    textarea.value = template ? renderWhatsappTemplate(template.content, vars) : defaultMessage;
  };

  const templates = await fetchWhatsappTemplates();
  templateSelect._templates = templates;
  if (templates.length > 0) {
    templateFieldWrap.style.display = "block";
    templateSelect.innerHTML =
      '<option value="">Mensagem automática</option>' +
      templates.map((t) => `<option value="${t.id}">${escapeHtml(t.name)}</option>`).join("");
  } else {
    templateFieldWrap.style.display = "none";
  }

  document.getElementById("sendWhatsappComposer").onclick = () => {
    const finalMessage = document.getElementById("whatsappComposerText").value;
    const opened = openWhatsApp(phone, finalMessage);
    backdrop.classList.add("hidden");
    if (opened && context && context.loanId) {
      const selected = templateSelect.selectedOptions[0];
      const template = templateSelect.value && selected ? selected.textContent : null;
      api
        .post(`/loans/${context.loanId}/whatsapp-charge`, { message: finalMessage, template })
        .then(() => typeof context.onLogged === "function" && context.onLogged())
        .catch(() => {});
    }
  };
  backdrop.classList.remove("hidden");
}

// Modal reutilizável pra trocar a senha de um usuário (operador/consultor)
// sem precisar saber a senha antiga — usado pelo gestor/admin.
async function openChangePasswordModal(targetUser, onSaved) {
  let backdrop = document.getElementById("changePasswordBackdrop");
  if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop hidden";
    backdrop.id = "changePasswordBackdrop";
    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h3>Trocar senha</h3>
          <button class="icon-btn" id="closeChangePassword" type="button">✕</button>
        </div>
        <p class="text-muted" id="changePasswordName" style="font-size:0.85rem;"></p>
        <div class="error-box hidden" id="changePasswordError"></div>
        <form id="changePasswordForm">
          <div class="field">
            <label for="changePasswordInput">Nova senha *</label>
            <input type="password" id="changePasswordInput" minlength="6" required />
          </div>
          <div class="form-actions">
            <button type="button" class="btn btn-outline" id="cancelChangePassword">Cancelar</button>
            <button type="submit" class="btn btn-primary">Salvar nova senha</button>
          </div>
        </form>
      </div>`;
    document.body.appendChild(backdrop);
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) backdrop.classList.add("hidden");
    });
    document.getElementById("closeChangePassword").addEventListener("click", () => backdrop.classList.add("hidden"));
    document.getElementById("cancelChangePassword").addEventListener("click", () => backdrop.classList.add("hidden"));
  }

  const form = document.getElementById("changePasswordForm");
  const errBox = document.getElementById("changePasswordError");
  form.reset();
  errBox.classList.add("hidden");
  document.getElementById("changePasswordName").textContent = `${targetUser.name} (${targetUser.email})`;

  form.onsubmit = async (ev) => {
    ev.preventDefault();
    try {
      await api.put(`/users/${targetUser.id}`, { password: document.getElementById("changePasswordInput").value });
      backdrop.classList.add("hidden");
      if (onSaved) onSaved();
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.remove("hidden");
    }
  };
  backdrop.classList.remove("hidden");
}

// Rótulos exibidos para cada permissão de Consultor (ver models.py
// ConsultantPermissions) — mesma ordem em todo lugar que os usar.
const CONSULTANT_PERMISSION_LABELS = [
  ["view_dashboard", "Ver Dashboard"],
  ["register_clients", "Cadastrar clientes"],
  ["register_loans", "Cadastrar empréstimos"],
  ["register_payments", "Registrar pagamentos"],
  ["edit_rates", "Editar taxa/multa do empréstimo"],
  ["settle_loans", "Quitar empréstimo antecipadamente"],
  ["view_reports", "Ver e exportar relatórios"],
  ["view_audit", "Ver auditoria"],
  ["send_whatsapp", "Enviar cobrança via WhatsApp"],
];

// Modal reutilizável (Administração e Particionamento) pra o gestor/admin
// habilitar, campo a campo, o que um usuário Consultor pode fazer no
// sistema. Busca o estado atual em /users/{id}/permissions e salva ao
// clicar em Salvar; `onSaved` é chamado depois de salvar com sucesso.
async function openConsultantPermissionsModal(targetUser, onSaved) {
  let backdrop = document.getElementById("consultantPermsBackdrop");
  if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop hidden";
    backdrop.id = "consultantPermsBackdrop";
    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h3>Permissões do consultor</h3>
          <button class="icon-btn" id="closeConsultantPerms" type="button">✕</button>
        </div>
        <p class="text-muted" id="consultantPermsName" style="font-size:0.85rem;"></p>
        <div class="error-box hidden" id="consultantPermsError"></div>
        <div class="permission-list" id="consultantPermsList"></div>
        <div class="form-actions">
          <button type="button" class="btn btn-outline" id="cancelConsultantPerms">Cancelar</button>
          <button type="button" class="btn btn-primary" id="saveConsultantPerms">Salvar</button>
        </div>
      </div>`;
    document.body.appendChild(backdrop);
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) backdrop.classList.add("hidden");
    });
    document.getElementById("closeConsultantPerms").addEventListener("click", () => backdrop.classList.add("hidden"));
    document.getElementById("cancelConsultantPerms").addEventListener("click", () => backdrop.classList.add("hidden"));
  }

  const errBox = document.getElementById("consultantPermsError");
  const list = document.getElementById("consultantPermsList");
  errBox.classList.add("hidden");
  document.getElementById("consultantPermsName").textContent = `${targetUser.name} (${targetUser.email})`;
  list.innerHTML = CONSULTANT_PERMISSION_LABELS.map(
    ([key, label]) => `
      <label class="permission-row">
        <input type="checkbox" data-perm="${key}" />
        <span>${escapeHtml(label)}</span>
      </label>`
  ).join("");

  try {
    const perms = await api.get(`/users/${targetUser.id}/permissions`);
    CONSULTANT_PERMISSION_LABELS.forEach(([key]) => {
      const input = list.querySelector(`input[data-perm="${key}"]`);
      if (input) input.checked = Boolean(perms[key]);
    });
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
  }

  document.getElementById("saveConsultantPerms").onclick = async () => {
    const payload = {};
    CONSULTANT_PERMISSION_LABELS.forEach(([key]) => {
      payload[key] = list.querySelector(`input[data-perm="${key}"]`).checked;
    });
    try {
      await api.put(`/users/${targetUser.id}/permissions`, payload);
      backdrop.classList.add("hidden");
      if (onSaved) onSaved();
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.remove("hidden");
    }
  };
  backdrop.classList.remove("hidden");
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
  const greeting = `Olá, ${loan.client.name}! Aqui é da equipe responsável pelo seu empréstimo (${formatOsNumber(loan.loan_number)}).`;
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

// Abre o compositor de WhatsApp para cobrar a próxima parcela em aberto de um
// empréstimo. `loan` precisa ser o detalhe completo (GET /loans/{id}: com
// client e installments). Usado pela página do empréstimo e pela lista. A cobrança
// aberta fica registrada no histórico da OS; onLogged() é chamado depois disso.
function openLoanCollectionComposer(loan, onLogged) {
  const nextInstallment = loan.installments.find((i) => i.status !== "pago");
  return openWhatsAppComposer(
    loan.client.phone,
    buildLoanCollectionMessage(loan),
    {
      cliente: loan.client.name,
      emprestimo: loan.loan_number,
      os: formatOsNumber(loan.loan_number),
      valor: nextInstallment
        ? formatMoney(Math.max(0, nextInstallment.base_amount + nextInstallment.late_fee_accrued - nextInstallment.paid_amount))
        : "",
      vencimento: nextInstallment ? formatDate(nextInstallment.due_date) : "",
      parcela: nextInstallment ? nextInstallment.number : "",
    },
    { loanId: loan.id, onLogged }
  );
}

// Número da Ordem de Serviço (OS) do empréstimo: OS-0001, OS-0002... É o próprio
// loan_number (sequencial por empresa, único, independente do cliente). Mantenha
// o formato igual a format_os_number() no backend (services/interest_engine.py).
function formatOsNumber(loanNumber) {
  return "OS-" + String(loanNumber).padStart(4, "0");
}

// O servidor manda data/hora em UTC sem fuso (ex.: 2026-09-18T18:39:27). Sem o "Z"
// o navegador leria como horário local e mostraria 3h errado (às vezes o dia errado).
function parseUtc(iso) {
  return new Date(/[zZ]$|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
}
function formatDateTime(iso) {
  return parseUtc(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
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

// textContent→innerHTML só escapa & < > — não as aspas. Sem escapá-las aqui, um
// valor com " quebraria qualquer atributo entre aspas (ex.: <option value="...">).
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

initTheme();
