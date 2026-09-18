document.getElementById("themeToggle").addEventListener("click", toggleTheme);
renderAppFooter(document.querySelector(".login-shell"));

function landingPage(user) {
  if (user.role === "consultor" && !consultorPerm(user, "view_dashboard")) return "/clientes.html";
  return "/dashboard.html";
}

if (getToken() && getUser()) {
  window.location.href = landingPage(getUser());
}

document.getElementById("loginForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const errorBox = document.getElementById("errorBox");
  const submitBtn = document.getElementById("submitBtn");
  errorBox.classList.add("hidden");
  submitBtn.disabled = true;
  submitBtn.textContent = "Entrando...";
  try {
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    const result = await api.post("/auth/login", { email, password });
    setSession(result.access_token, result.user);
    window.location.href = landingPage(result.user);
  } catch (err) {
    errorBox.textContent = err.message || "Não foi possível entrar";
    errorBox.classList.remove("hidden");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Entrar";
  }
});
