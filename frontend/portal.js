(() => {
  const setMessage = (element, text, isError = false) => {
    if (!element) return;
    element.textContent = text;
    element.classList.toggle("is-error", isError);
    element.classList.toggle("is-success", !isError);
  };

  async function requestJson(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `Request failed (${response.status}).`);
    }
    return payload;
  }

  const loginForm = document.getElementById("portal-login-form");
  if (loginForm) {
    const adminMode = new URLSearchParams(location.search).get("role") === "admin";
    const heading = document.getElementById("login-heading");
    const eyebrow = document.getElementById("login-eyebrow");
    const button = loginForm.querySelector("button[type='submit']");
    const message = document.getElementById("login-message");

    if (adminMode) {
      heading.textContent = "Administrator sign in";
      eyebrow.textContent = "PRIVILEGED ACCESS / ADMINISTRATOR";
      button.firstChild.textContent = "Sign in as administrator ";
    }

    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!loginForm.reportValidity()) return;
      button.disabled = true;
      setMessage(message, "Authenticating...");
      try {
        const user = await requestJson("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: loginForm.elements.username.value.trim(),
            password: loginForm.elements.password.value,
          }),
        });
        if (adminMode && user.role !== "admin") {
          throw new Error("This account does not have administrator access.");
        }
        localStorage.setItem("ct_auth_user", JSON.stringify(user));
        location.replace("/");
      } catch (error) {
        setMessage(message, error.message || "Could not reach the sign-in service.", true);
        button.disabled = false;
      }
    });
  }

  const registerForm = document.getElementById("portal-register-form");
  if (registerForm) {
    const button = registerForm.querySelector("button[type='submit']");
    const message = document.getElementById("register-message");
    registerForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!registerForm.reportValidity()) return;
      const password = registerForm.elements.password.value;
      if (password !== registerForm.elements.confirm_password.value) {
        setMessage(message, "The passwords do not match.", true);
        return;
      }
      button.disabled = true;
      setMessage(message, "Creating account...");
      try {
        const user = await requestJson("/api/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            full_name: registerForm.elements.full_name.value.trim(),
            username: registerForm.elements.username.value.trim(),
            email: registerForm.elements.email.value.trim(),
            password,
          }),
        });
        localStorage.setItem("ct_auth_user", JSON.stringify(user));
        location.replace("/");
      } catch (error) {
        setMessage(message, error.message || "Could not reach the registration service.", true);
        button.disabled = false;
      }
    });
  }

  const healthElement = document.getElementById("portal-health");
  if (healthElement) {
    Promise.all([
      requestJson("/api/health"),
      requestJson("/api/trials"),
    ]).then(([health, trial]) => {
      healthElement.textContent = `Service ${health.status} · ${health.database} database · ${health.trace_loaded ? "model loaded" : "model unavailable"}`;
      healthElement.classList.add("is-online");
      document.getElementById("about-trial").textContent = trial.trial_id;
      document.getElementById("about-sites").textContent = trial.total_sites.toLocaleString();
      document.getElementById("about-countries").textContent = trial.countries.length.toLocaleString();
      document.getElementById("about-database").textContent = health.database.toUpperCase();
      document.getElementById("about-model").textContent = health.model_type;
      document.getElementById("about-trace").textContent = `Model trace: ${health.trace_loaded ? "loaded" : "unavailable"}`;
    }).catch(() => {
      healthElement.textContent = "Forecasting service unavailable";
      healthElement.classList.add("is-offline");
      document.getElementById("about-trace").textContent = "Model trace status: unavailable";
    });
  }
})();
