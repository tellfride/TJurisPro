const API_BASE = "/api";

function getToken() {
  return localStorage.getItem("jurispro_token");
}

function getUser() {
  const raw = localStorage.getItem("jurispro_user");
  return raw ? JSON.parse(raw) : null;
}

function setSession(token, user) {
  localStorage.setItem("jurispro_token", token);
  localStorage.setItem("jurispro_user", JSON.stringify(user));
}

function clearSession() {
  localStorage.removeItem("jurispro_token");
  localStorage.removeItem("jurispro_user");
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = Object.assign(
    { "Content-Type": "application/json" },
    options.headers || {}
  );
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(API_BASE + path, { ...options, headers });

  if (response.status === 401) {
    clearSession();
    window.location.href = "/index.html";
    throw new Error("Sessão expirada");
  }

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (e) {
      data = null;
    }
  }

  if (!response.ok) {
    const message = (data && data.detail) || "Erro inesperado";
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return data;
}

const api = {
  get: (path) => apiFetch(path),
  post: (path, body) => apiFetch(path, { method: "POST", body: JSON.stringify(body) }),
  put: (path, body) => apiFetch(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: (path) => apiFetch(path, { method: "DELETE" }),
};

// Baixa um arquivo do backend (ex: .xlsx) autenticado e dispara o "Salvar como"
// do navegador. Um <a href> comum não consegue mandar o header Authorization,
// por isso buscamos como blob e criamos um link temporário.
async function downloadFile(path, fallbackFilename) {
  const token = getToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(API_BASE + path, { headers });

  if (response.status === 401) {
    clearSession();
    window.location.href = "/index.html";
    throw new Error("Sessão expirada");
  }
  if (!response.ok) {
    let message = "Erro ao baixar arquivo";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch (e) {}
    throw new Error(message);
  }

  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : fallbackFilename;

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// Envia um arquivo (multipart/form-data) autenticado, ex: upload de planilha.
async function uploadFile(path, file) {
  const token = getToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(API_BASE + path, { method: "POST", headers, body: formData });

  if (response.status === 401) {
    clearSession();
    window.location.href = "/index.html";
    throw new Error("Sessão expirada");
  }

  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (e) {}

  if (!response.ok) {
    const message = (data && data.detail) || "Erro ao enviar arquivo";
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return data;
}
