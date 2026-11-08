/**
 * Clinical Trial Enrollment Forecasting Dashboard
 * Reactive Multi-Tab UI with Inline SVG Fan Chart, Histogram, What-If Simulation Sandbox,
 * Real-World Hospital Flow Analytics, Bayesian Model Diagnostics, and Role-Based Management.
 */

// Application State
const state = {
  currentWeek: 40,
  target: 1200,
  deadline: 90,
  flowChange: 0.0,
  newSites: 0,
  closedSites: new Set(),
  siteFilter: "ALL",
  countryFilter: "ALL",
  searchQuery: "",
  theme: localStorage.getItem("ct_theme") || "dark",
  forecastData: null,
  baselineData: null,
  sites: [],
  selectedSiteId: null,
  currentUser: JSON.parse(localStorage.getItem("ct_auth_user") || "null") || {
    username: "investigator",
    full_name: "Dr. Sarah Chen",
    role: "user",
    title: "Clinical Investigator",
    email: "sarah.chen@trial-site.org",
  },
};

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initAuth();
  initEventListeners();
  checkHealth();
  fetchTrialMetadata();
  fetchInitialData();
});

// Theme Management
function initTheme() {
  document.documentElement.setAttribute("data-theme", state.theme);
  updateThemeButton();
}

function toggleTheme() {
  state.theme = state.theme === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", state.theme);
  localStorage.setItem("ct_theme", state.theme);
  updateThemeButton();
  if (state.forecastData) {
    renderFanChart(state.forecastData);
    renderHistogram(state.forecastData);
  }
}

function updateThemeButton() {
  const btnText = document.getElementById("theme-text");
  if (btnText) {
    btnText.textContent = state.theme === "dark" ? "Light Mode" : "Dark Mode";
  }
}

// Event Listeners
function initEventListeners() {
  document.getElementById("theme-toggle")?.addEventListener("click", toggleTheme);

  // Dashboard Tab Switching
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      switchTab(tabId);
    });
  });

  // Sliders and Inputs
  const targetInput = document.getElementById("input-target");
  targetInput?.addEventListener("change", (e) => {
    state.target = parseInt(e.target.value) || 1200;
    triggerForecast();
  });

  const deadlineInput = document.getElementById("input-deadline");
  deadlineInput?.addEventListener("change", (e) => {
    state.deadline = parseInt(e.target.value) || 90;
    triggerForecast();
  });

  const flowSlider = document.getElementById("slider-flow");
  flowSlider?.addEventListener("input", (e) => {
    const val = parseInt(e.target.value);
    state.flowChange = val / 100.0;
    document.getElementById("flow-val").textContent = `${val >= 0 ? "+" : ""}${val}%`;
    triggerForecast();
  });

  const newSitesSlider = document.getElementById("slider-new-sites");
  newSitesSlider?.addEventListener("input", (e) => {
    state.newSites = parseInt(e.target.value);
    document.getElementById("new-sites-val").textContent = `${state.newSites} sites`;
    triggerForecast();
  });

  // Quick Scenario Presets
  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const isPrivileged = state.currentUser && (state.currentUser.role === "management" || state.currentUser.role === "admin");
      if (!isPrivileged) {
        showToast("⚠️ Quick scenarios require Management or Admin privileges.", "warning");
        return;
      }
      const flow = parseInt(btn.getAttribute("data-flow")) || 0;
      const sites = parseInt(btn.getAttribute("data-sites")) || 0;
      state.flowChange = flow / 100.0;
      state.newSites = sites;

      const flowSliderElem = document.getElementById("slider-flow");
      const newSitesSliderElem = document.getElementById("slider-new-sites");
      if (flowSliderElem) flowSliderElem.value = flow;
      if (newSitesSliderElem) newSitesSliderElem.value = sites;
      document.getElementById("flow-val").textContent = `${flow >= 0 ? "+" : ""}${flow}%`;
      document.getElementById("new-sites-val").textContent = `${sites} sites`;

      showToast(`Applied preset: ${btn.textContent.trim()}`);
      triggerForecast();
    });
  });

  document.getElementById("btn-close-at-risk")?.addEventListener("click", () => {
    const isPrivileged = state.currentUser && (state.currentUser.role === "management" || state.currentUser.role === "admin");
    if (!isPrivileged) {
      showToast("⚠️ Simulation interventions require Management or Admin privileges.", "warning");
      return;
    }
    if (!state.forecastData) return;
    state.forecastData.sites.forEach((s) => {
      if (s.is_at_risk) {
        state.closedSites.add(s.site_id);
      }
    });
    showToast("Closed all at-risk sites. Recalculating forecast...");
    triggerForecast();
  });

  document.getElementById("btn-reset")?.addEventListener("click", () => {
    const isPrivileged = state.currentUser && (state.currentUser.role === "management" || state.currentUser.role === "admin");
    if (!isPrivileged) {
      showToast("⚠️ Simulation interventions require Management or Admin privileges.", "warning");
      return;
    }
    state.flowChange = 0.0;
    state.newSites = 0;
    state.closedSites.clear();
    document.getElementById("slider-flow").value = "0";
    document.getElementById("flow-val").textContent = "+0%";
    document.getElementById("slider-new-sites").value = "0";
    document.getElementById("new-sites-val").textContent = "0 sites";
    showToast("Interventions reset to Status Quo.");
    triggerForecast();
  });

  // Table Search and Filter
  document.getElementById("site-search")?.addEventListener("input", (e) => {
    state.searchQuery = e.target.value.toLowerCase();
    renderSitesTable();
  });

  document.getElementById("status-filter")?.addEventListener("change", (e) => {
    state.siteFilter = e.target.value;
    renderSitesTable();
  });

  document.getElementById("country-filter")?.addEventListener("change", (e) => {
    state.countryFilter = e.target.value;
    renderSitesTable();
  });

  // Auth & Role Event Listeners
  document.getElementById("btn-open-login")?.addEventListener("click", openLoginModal);
  document.getElementById("btn-close-login")?.addEventListener("click", closeLoginModal);
  document.getElementById("btn-cancel-login")?.addEventListener("click", () => {
    setAuthenticatedUser({
      username: "guest_investigator",
      full_name: "Guest Investigator",
      role: "user",
      title: "Clinical Investigator (Guest)",
      email: "guest@trial.org",
    });
    closeLoginModal();
    showToast("Signed in as Guest (User View).");
  });

  document.getElementById("btn-quick-login-admin")?.addEventListener("click", () => quickLogin("admin"));
  document.getElementById("btn-quick-login-mgmt")?.addEventListener("click", () => quickLogin("management"));
  document.getElementById("btn-quick-login-user")?.addEventListener("click", () => quickLogin("user"));

  document.getElementById("btn-switch-role")?.addEventListener("click", switchRole);
  document.getElementById("btn-logout")?.addEventListener("click", logout);
  document.getElementById("link-switch-to-manager")?.addEventListener("click", (e) => {
    e.preventDefault();
    quickLogin("management");
  });

  // Demo credential chips
  document.getElementById("chip-admin")?.addEventListener("click", () => {
    document.getElementById("login-username").value = "admin";
    document.getElementById("login-password").value = "admin123";
  });
  document.getElementById("chip-vijayaraj")?.addEventListener("click", () => {
    document.getElementById("login-username").value = "vijayaraj";
    document.getElementById("login-password").value = "admin123";
  });
  document.getElementById("chip-manager")?.addEventListener("click", () => {
    document.getElementById("login-username").value = "manager";
    document.getElementById("login-password").value = "admin123";
  });
  document.getElementById("chip-user")?.addEventListener("click", () => {
    document.getElementById("login-username").value = "user";
    document.getElementById("login-password").value = "user123";
  });

  // Change Password Modal Listeners
  document.getElementById("btn-change-pwd")?.addEventListener("click", openChangePwdModal);
  document.getElementById("btn-close-pwd-modal")?.addEventListener("click", closeChangePwdModal);
  document.getElementById("btn-cancel-change-pwd")?.addEventListener("click", closeChangePwdModal);
  document.getElementById("change-pwd-form")?.addEventListener("submit", submitChangePwd);

  // Login form submit
  document.getElementById("login-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const u = document.getElementById("login-username").value.trim();
    const p = document.getElementById("login-password").value.trim();
    if (u && p) {
      loginWithCredentials(u, p);
    }
  });

  // Ingestion Modal Listeners (Management)
  document.getElementById("btn-open-ingest")?.addEventListener("click", openIngestModal);
  document.getElementById("btn-close-ingest")?.addEventListener("click", closeIngestModal);
  document.getElementById("btn-cancel-ingest")?.addEventListener("click", closeIngestModal);
  document.getElementById("ingest-form")?.addEventListener("submit", submitIngestData);

  // Site Detail Modal Listeners
  document.getElementById("btn-close-site-modal")?.addEventListener("click", closeSiteDetailModal);
  document.getElementById("btn-modal-dismiss")?.addEventListener("click", closeSiteDetailModal);
  document.getElementById("btn-modal-toggle-site")?.addEventListener("click", () => {
    if (state.selectedSiteId) {
      toggleSiteAction(state.selectedSiteId);
      closeSiteDetailModal();
    }
  });
}

// Tab Switching
function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === tabId);
  });
  document.querySelectorAll(".tab-content").forEach((content) => {
    content.classList.toggle("active", content.id === tabId);
  });

  if (tabId === "tab-overview" && state.forecastData) {
    setTimeout(() => {
      renderFanChart(state.forecastData);
      renderHistogram(state.forecastData);
    }, 50);
  }
}

// Authentication & Role Functions
function initAuth() {
  updateUserDisplay();
  applyRolePermissions();
}

function updateUserDisplay() {
  const profileBadge = document.getElementById("user-profile-badge");
  const openLoginBtn = document.getElementById("btn-open-login");
  const displayName = document.getElementById("user-display-name");
  const roleBadge = document.getElementById("user-role-badge");
  const avatar = document.getElementById("user-avatar");
  const changePwdBtn = document.getElementById("btn-change-pwd");

  if (!state.currentUser) {
    if (profileBadge) profileBadge.style.display = "none";
    if (openLoginBtn) openLoginBtn.style.display = "inline-flex";
    return;
  }

  if (openLoginBtn) openLoginBtn.style.display = "none";
  if (profileBadge) profileBadge.style.display = "flex";

  if (displayName) displayName.textContent = state.currentUser.full_name || state.currentUser.username;

  const role = state.currentUser.role;
  const isAdmin = role === "admin";
  const isMgmt = role === "management";

  if (roleBadge) {
    if (isAdmin) {
      roleBadge.textContent = "👑 System Admin";
      roleBadge.className = "role-badge role-admin";
    } else if (isMgmt) {
      roleBadge.textContent = "Management";
      roleBadge.className = "role-badge role-mgmt";
    } else {
      roleBadge.textContent = "Investigator";
      roleBadge.className = "role-badge role-user";
    }
  }

  if (avatar) {
    avatar.textContent = isAdmin ? "👑" : isMgmt ? "🛡️" : "👨‍⚕️";
  }

  if (changePwdBtn) {
    changePwdBtn.style.display = "inline-block";
  }
}

function applyRolePermissions() {
  const isPrivileged = state.currentUser && (state.currentUser.role === "management" || state.currentUser.role === "admin");
  const isAdmin = state.currentUser && state.currentUser.role === "admin";
  const isMgmt = state.currentUser && state.currentUser.role === "management";

  const rolePill = document.getElementById("panel-role-pill");
  const userNotice = document.getElementById("user-role-notice");
  const openIngestBtn = document.getElementById("btn-open-ingest");
  const controlsGrid = document.getElementById("controls-grid");

  if (rolePill) {
    if (isAdmin) {
      rolePill.textContent = "👑 Admin Superuser Mode (Full Engine Access)";
      rolePill.className = "role-pill admin";
    } else if (isMgmt) {
      rolePill.textContent = "🛡️ Management Mode (Full Simulation)";
      rolePill.className = "role-pill mgmt";
    } else {
      rolePill.textContent = "User View (Read-Only)";
      rolePill.className = "role-pill";
    }
  }

  if (userNotice) {
    userNotice.style.display = isPrivileged ? "none" : "flex";
  }

  if (openIngestBtn) {
    openIngestBtn.style.display = isPrivileged ? "inline-flex" : "none";
  }

  const inputs = [
    document.getElementById("input-target"),
    document.getElementById("input-deadline"),
    document.getElementById("slider-flow"),
    document.getElementById("slider-new-sites"),
    document.getElementById("btn-close-at-risk"),
    document.getElementById("btn-reset"),
  ];

  inputs.forEach((elem) => {
    if (elem) elem.disabled = !isPrivileged;
  });

  if (controlsGrid) {
    if (!isPrivileged) {
      controlsGrid.classList.add("sandbox-disabled");
    } else {
      controlsGrid.classList.remove("sandbox-disabled");
    }
  }

  renderSitesTable();
}

function setAuthenticatedUser(user) {
  state.currentUser = user;
  localStorage.setItem("ct_auth_user", JSON.stringify(user));
  updateUserDisplay();
  applyRolePermissions();
}

function openLoginModal() {
  const modal = document.getElementById("login-modal");
  if (modal) modal.style.display = "flex";
  const errDiv = document.getElementById("login-error");
  if (errDiv) errDiv.style.display = "none";
}

function closeLoginModal() {
  const modal = document.getElementById("login-modal");
  if (modal) modal.style.display = "none";
}

async function loginWithCredentials(username, password) {
  const errDiv = document.getElementById("login-error");
  if (errDiv) errDiv.style.display = "none";

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: "Authentication failed." }));
      throw new Error(errData.detail || "Invalid username or password.");
    }

    const user = await res.json();
    setAuthenticatedUser(user);
    closeLoginModal();
    showToast(`Signed in as ${user.full_name} [${user.role.toUpperCase()}]`);
  } catch (err) {
    if (errDiv) {
      errDiv.textContent = err.message;
      errDiv.style.display = "block";
    }
  }
}

function quickLogin(role) {
  if (role === "admin") {
    loginWithCredentials("admin", "admin123");
  } else if (role === "management") {
    loginWithCredentials("manager", "admin123");
  } else {
    loginWithCredentials("investigator", "user123");
  }
}

function switchRole() {
  const currentRole = state.currentUser ? state.currentUser.role : "user";
  if (currentRole === "user") {
    quickLogin("management");
  } else if (currentRole === "management") {
    quickLogin("admin");
  } else {
    quickLogin("user");
  }
}

function logout() {
  state.currentUser = null;
  localStorage.removeItem("ct_auth_user");
  updateUserDisplay();
  applyRolePermissions();
  openLoginModal();
  showToast("Logged out.");
}

function openChangePwdModal() {
  const modal = document.getElementById("change-pwd-modal");
  if (!modal) return;
  modal.style.display = "flex";
  const sub = document.getElementById("pwd-modal-user-subtitle");
  if (sub && state.currentUser) {
    sub.textContent = `Update credentials for @${state.currentUser.username} (${state.currentUser.role})`;
  }
  const errDiv = document.getElementById("change-pwd-error");
  if (errDiv) errDiv.style.display = "none";
  const oldInput = document.getElementById("pwd-old");
  const newInput = document.getElementById("pwd-new");
  if (oldInput) oldInput.value = "";
  if (newInput) newInput.value = "";
}

function closeChangePwdModal() {
  const modal = document.getElementById("change-pwd-modal");
  if (modal) modal.style.display = "none";
}

async function submitChangePwd(e) {
  e.preventDefault();
  if (!state.currentUser) return;
  const oldPwd = document.getElementById("pwd-old").value;
  const newPwd = document.getElementById("pwd-new").value;
  const errDiv = document.getElementById("change-pwd-error");

  try {
    const res = await fetch("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: state.currentUser.username,
        old_password: oldPwd,
        new_password: newPwd,
      }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({ detail: "Failed to update password." }));
      throw new Error(data.detail || "Incorrect current password.");
    }

    closeChangePwdModal();
    showToast("✓ Password successfully updated!");
  } catch (err) {
    if (errDiv) {
      errDiv.textContent = err.message;
      errDiv.style.display = "block";
    }
  }
}

function openIngestModal() {
  const modal = document.getElementById("ingest-modal");
  if (modal) modal.style.display = "flex";
}

function closeIngestModal() {
  const modal = document.getElementById("ingest-modal");
  if (modal) modal.style.display = "none";
}

async function submitIngestData(e) {
  e.preventDefault();
  const site = document.getElementById("ingest-site").value;
  const week = parseInt(document.getElementById("ingest-week").value) || 41;
  const enrolled = parseInt(document.getElementById("ingest-enrolled").value) || 0;
  const volume = parseInt(document.getElementById("ingest-volume").value) || 40;
  const statusMsg = document.getElementById("ingest-status-msg");

  const payload = {
    records: [
      {
        site_id: site,
        week: week,
        enrolled_count: enrolled,
        eligible_volume: volume,
        is_active: 1,
      },
    ],
    recalculate_forecast: true,
  };

  try {
    if (statusMsg) {
      statusMsg.style.display = "block";
      statusMsg.style.color = "var(--text-muted)";
      statusMsg.textContent = "Ingesting record and re-running Bayesian forecast...";
    }

    const res = await fetch("/api/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error("Data ingestion failed.");
    const data = await res.json();

    closeIngestModal();
    showToast(`✓ Ingested week ${week} for ${site}. Forecast updated!`);
    await triggerForecast();
  } catch (err) {
    if (statusMsg) {
      statusMsg.style.display = "block";
      statusMsg.style.color = "var(--accent-red)";
      statusMsg.textContent = err.message;
    }
  }
}

function showToast(message, type = "info") {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.style.display = "block";
  if (type === "warning") {
    toast.style.borderColor = "var(--accent-amber)";
  } else {
    toast.style.borderColor = "var(--accent-blue)";
  }
  setTimeout(() => {
    toast.style.display = "none";
  }, 3500);
}

// Health Check
async function checkHealth() {
  const badge = document.getElementById("system-badge");
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.status === "ok" || data.status === "healthy") {
      badge.textContent = `Online (${data.model_type})`;
      badge.classList.remove("pulse");
    }
  } catch (err) {
    badge.textContent = "Offline / Error";
    badge.style.color = "var(--accent-red)";
  }
}

// Fetch Trial Metadata
async function fetchTrialMetadata() {
  try {
    const res = await fetch("/api/trials");
    if (!res.ok) return;
    const data = await res.json();

    const titleElem = document.getElementById("protocol-title");
    if (titleElem) titleElem.textContent = `${data.title} (${data.trial_id})`;

    const countriesList = document.getElementById("protocol-countries-list");
    if (countriesList && data.countries) {
      countriesList.innerHTML = data.countries
        .map((c) => `<span class="protocol-chip">🌐 ${c}</span>`)
        .join("");
    }
  } catch (err) {
    console.warn("Trial metadata fetch failed:", err);
  }
}

// Initial Data Fetch
async function fetchInitialData() {
  await triggerForecast(true);
}

// Trigger Forecast / What-If API
async function triggerForecast(isInitial = false) {
  const reqBody = {
    current_week: state.currentWeek,
    target: state.target,
    deadline: state.deadline,
    flow_change: state.flowChange,
    new_sites: state.newSites,
    closed: Array.from(state.closedSites),
    draws: 1000,
  };

  try {
    const res = await fetch("/api/whatif", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(reqBody),
    });

    const data = await res.json();
    state.baselineData = data.baseline;
    state.forecastData = data.scenario;
    state.sites = data.scenario.sites;

    updateKPIs(data.scenario);
    updateTrialProgressBar(data.scenario.total_enrolled_to_date, data.scenario.target);
    updateScenarioBadge(data);
    updateComparisonCards(data);
    renderFanChart(data.scenario);
    renderHistogram(data.scenario);
    renderSitesTable();
  } catch (err) {
    console.error("Failed to execute forecast:", err);
  }
}

// Update Top KPI Cards
function updateKPIs(data) {
  document.getElementById("kpi-enrolled").textContent = data.total_enrolled_to_date.toLocaleString();
  document.getElementById("kpi-target").textContent = data.target.toLocaleString();
  document.getElementById("kpi-deadline-sub").textContent = `Deadline: Week ${data.deadline}`;

  const probElem = document.getElementById("kpi-prob");
  const pVal = Math.round(data.p_hit_by_deadline * 100);
  probElem.textContent = `${pVal}%`;
  probElem.style.color = pVal >= 80 ? "var(--accent-green)" : pVal >= 50 ? "var(--accent-amber)" : "var(--accent-red)";

  document.getElementById("kpi-comp-week").textContent = `Week ${data.median_completion_week}`;
  const diffWeeks = (data.median_completion_week - data.deadline).toFixed(1);
  const diffElem = document.getElementById("kpi-comp-delta");
  if (diffWeeks <= 0) {
    diffElem.textContent = `${Math.abs(diffWeeks)} weeks ahead of deadline`;
    diffElem.style.color = "var(--accent-green)";
  } else {
    diffElem.textContent = `${diffWeeks} weeks delayed past deadline`;
    diffElem.style.color = "var(--accent-red)";
  }

  document.getElementById("kpi-risk-sites").textContent = data.at_risk_sites_count;
  document.getElementById("kpi-active-sites").textContent = `${data.active_sites_count} Active Sites`;

  // Site summary pills
  const totalElem = document.getElementById("site-stat-total");
  const activeElem = document.getElementById("site-stat-active");
  const riskElem = document.getElementById("site-stat-risk");
  const closedElem = document.getElementById("site-stat-closed");
  const tabSiteCount = document.getElementById("tab-site-count");

  if (totalElem) totalElem.textContent = data.sites.length;
  if (activeElem) activeElem.textContent = data.active_sites_count;
  if (riskElem) riskElem.textContent = data.at_risk_sites_count;
  if (closedElem) closedElem.textContent = state.closedSites.size;
  if (tabSiteCount) tabSiteCount.textContent = data.sites.length;
}

// Update Progress Bar
function updateTrialProgressBar(enrolled, target) {
  const pct = Math.min(Math.round((enrolled / target) * 100), 100);
  const enrolledText = document.getElementById("progress-enrolled-text");
  const targetText = document.getElementById("progress-target-text");
  const pctText = document.getElementById("progress-percent-text");
  const fillElem = document.getElementById("progress-bar-fill");

  if (enrolledText) enrolledText.textContent = enrolled.toLocaleString();
  if (targetText) targetText.textContent = target.toLocaleString();
  if (pctText) pctText.textContent = `${pct}% target achieved`;
  if (fillElem) fillElem.style.width = `${pct}%`;
}

// Update Scenario Description Banner
function updateScenarioBadge(whatif) {
  const badge = document.getElementById("scenario-tag");
  const banner = document.getElementById("whatif-delta-banner");

  const isIntervention = state.flowChange !== 0 || state.newSites > 0 || state.closedSites.size > 0;
  if (!isIntervention) {
    badge.textContent = "Status Quo";
    badge.style.color = "var(--accent-blue)";
    banner.style.display = "none";
  } else {
    badge.textContent = "Intervention Active";
    badge.style.color = "var(--accent-amber)";
    banner.style.display = "block";

    const compDelta = whatif.delta_completion_week;
    const probDelta = Math.round(whatif.delta_p_hit_by_deadline * 100);

    const compSpan = document.getElementById("delta-comp-text");
    compSpan.textContent = `Completion: ${compDelta >= 0 ? "+" : ""}${compDelta} weeks vs Baseline`;
    compSpan.style.color = compDelta <= 0 ? "var(--accent-green)" : "var(--accent-red)";

    const probSpan = document.getElementById("delta-prob-text");
    probSpan.textContent = `P(Hit Deadline): ${probDelta >= 0 ? "+" : ""}${probDelta}% vs Baseline`;
    probSpan.style.color = probDelta >= 0 ? "var(--accent-green)" : "var(--accent-red)";
  }
}

// Update What-If Comparison Cards
function updateComparisonCards(whatif) {
  const baseProb = document.getElementById("compare-base-prob");
  const baseWeek = document.getElementById("compare-base-week");
  const baseSites = document.getElementById("compare-base-sites");

  const scenProb = document.getElementById("compare-scen-prob");
  const scenWeek = document.getElementById("compare-scen-week");
  const netDelta = document.getElementById("compare-net-delta");

  if (baseProb) baseProb.textContent = `${Math.round(whatif.baseline.p_hit_by_deadline * 100)}%`;
  if (baseWeek) baseWeek.textContent = `Week ${whatif.baseline.median_completion_week}`;
  if (baseSites) baseSites.textContent = `${whatif.baseline.active_sites_count} Sites`;

  if (scenProb) scenProb.textContent = `${Math.round(whatif.scenario.p_hit_by_deadline * 100)}%`;
  if (scenWeek) scenWeek.textContent = `Week ${whatif.scenario.median_completion_week}`;

  if (netDelta) {
    const d = whatif.delta_completion_week;
    if (d < 0) {
      netDelta.textContent = `⚡ ${Math.abs(d)} weeks faster`;
      netDelta.style.color = "var(--accent-green)";
    } else if (d > 0) {
      netDelta.textContent = `⚠️ +${d} weeks slower`;
      netDelta.style.color = "var(--accent-red)";
    } else {
      netDelta.textContent = `0 weeks (Unchanged)`;
      netDelta.style.color = "var(--text-secondary)";
    }
  }
}

// Render SVG Bayesian Fan Chart
function renderFanChart(data) {
  const svg = document.getElementById("fan-chart-svg");
  if (!svg || !data.forecast_fan) return;

  const width = 850;
  const height = 360;
  const pad = { top: 25, right: 30, bottom: 40, left: 60 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const fan = data.forecast_fan;
  const obs = data.observed_history;

  const minWeek = 1;
  const maxWeek = 104;
  const maxEnroll = Math.max(data.target * 1.15, fan.q975[fan.q975.length - 1] * 1.05);

  const scaleX = (w) => pad.left + ((w - minWeek) / (maxWeek - minWeek)) * plotW;
  const scaleY = (y) => pad.top + plotH - (y / maxEnroll) * plotH;

  let svgContent = "";

  // Grid lines
  for (let e = 200; e <= maxEnroll; e += 200) {
    const yPos = scaleY(e);
    svgContent += `<line x1="${pad.left}" y1="${yPos}" x2="${width - pad.right}" y2="${yPos}" class="grid-line" />`;
    svgContent += `<text x="${pad.left - 8}" y="${yPos + 4}" text-anchor="end" class="axis-text">${e}</text>`;
  }

  for (let w = 10; w <= 100; w += 10) {
    const xPos = scaleX(w);
    svgContent += `<line x1="${xPos}" y1="${pad.top}" x2="${xPos}" y2="${pad.top + plotH}" class="grid-line" />`;
    svgContent += `<text x="${xPos}" y="${height - 15}" text-anchor="middle" class="axis-text">W${w}</text>`;
  }

  // Helper for polygon ribbon
  const makeRibbon = (qLow, qHigh) => {
    let pts = [];
    if (obs.length > 0) {
      const lastObs = obs[obs.length - 1];
      pts.push(`${scaleX(lastObs.week)},${scaleY(lastObs.cumulative_enrolled)}`);
    }
    fan.weeks.forEach((w, i) => pts.push(`${scaleX(w)},${scaleY(qHigh[i])}`));
    for (let i = fan.weeks.length - 1; i >= 0; i--) {
      pts.push(`${scaleX(fan.weeks[i])},${scaleY(qLow[i])}`);
    }
    return pts.join(" ");
  };

  // 95% Credible Band
  svgContent += `<polygon points="${makeRibbon(fan.q025, fan.q975)}" class="fan-area-95" />`;
  // 80% Credible Band
  svgContent += `<polygon points="${makeRibbon(fan.q10, fan.q90)}" class="fan-area-80" />`;

  // Target Line
  const targetY = scaleY(data.target);
  svgContent += `<line x1="${pad.left}" y1="${targetY}" x2="${width - pad.right}" y2="${targetY}" stroke="var(--line-target)" stroke-width="2" stroke-dasharray="4,4" />`;
  svgContent += `<text x="${width - pad.right - 5}" y="${targetY - 6}" text-anchor="end" fill="var(--line-target)" font-size="11" font-weight="600">Target: ${data.target}</text>`;

  // Deadline Line
  const deadlineX = scaleX(data.deadline);
  svgContent += `<line x1="${deadlineX}" y1="${pad.top}" x2="${deadlineX}" y2="${pad.top + plotH}" stroke="var(--line-deadline)" stroke-width="2" stroke-dasharray="4,4" />`;
  svgContent += `<text x="${deadlineX}" y="${pad.top + 14}" text-anchor="middle" fill="var(--line-deadline)" font-size="11" font-weight="600">Deadline (W${data.deadline})</text>`;

  // Observed Curve
  let obsPath = "";
  obs.forEach((d, i) => {
    const x = scaleX(d.week);
    const y = scaleY(d.cumulative_enrolled);
    obsPath += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
  });
  svgContent += `<path d="${obsPath}" class="trajectory-line-observed" />`;

  // Median (q50) Forecast Line
  let medPath = "";
  if (obs.length > 0) {
    const lastObs = obs[obs.length - 1];
    medPath = `M ${scaleX(lastObs.week)} ${scaleY(lastObs.cumulative_enrolled)}`;
  }
  fan.weeks.forEach((w, i) => {
    const x = scaleX(w);
    const y = scaleY(fan.q50[i]);
    medPath += medPath === "" ? `M ${x} ${y}` : ` L ${x} ${y}`;
  });
  svgContent += `<path d="${medPath}" class="trajectory-line-median" />`;

  svg.innerHTML = svgContent;
}

// Render SVG Completion Week Histogram
function renderHistogram(data) {
  const svg = document.getElementById("hist-chart-svg");
  if (!svg || !data.completion_histogram) return;

  const width = 450;
  const height = 360;
  const pad = { top: 25, right: 20, bottom: 40, left: 45 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const bins = data.completion_histogram;
  if (bins.length === 0) return;

  const minW = bins[0].week;
  const maxW = bins[bins.length - 1].week + 2;
  const maxCount = Math.max(...bins.map((b) => b.count), 1);

  const scaleX = (w) => pad.left + ((w - minW) / (maxW - minW)) * plotW;
  const scaleY = (c) => pad.top + plotH - (c / maxCount) * plotH;
  const barW = Math.max(plotW / bins.length - 3, 4);

  let svgContent = "";

  // Grid
  svgContent += `<line x1="${pad.left}" y1="${pad.top + plotH}" x2="${width - pad.right}" y2="${pad.top + plotH}" class="axis-line" />`;

  // Bars
  bins.forEach((b) => {
    const x = scaleX(b.week);
    const y = scaleY(b.count);
    const h = pad.top + plotH - y;
    const isPastDeadline = b.week > data.deadline;
    const barColor = isPastDeadline ? "var(--accent-red)" : "var(--accent-blue)";
    svgContent += `<rect x="${x}" y="${y}" width="${barW}" height="${h}" fill="${barColor}" rx="2" opacity="0.85" />`;
    if (b.week % 8 === 0) {
      svgContent += `<text x="${x + barW / 2}" y="${height - 15}" text-anchor="middle" class="axis-text">${b.week}</text>`;
    }
  });

  // Deadline Line
  const deadlineX = scaleX(data.deadline);
  svgContent += `<line x1="${deadlineX}" y1="${pad.top}" x2="${deadlineX}" y2="${pad.top + plotH}" stroke="var(--line-deadline)" stroke-width="2" stroke-dasharray="3,3" />`;
  svgContent += `<text x="${deadlineX}" y="${pad.top - 8}" text-anchor="middle" fill="var(--line-deadline)" font-size="10" font-weight="600">Deadline</text>`;

  svg.innerHTML = svgContent;
}

// Render Sites Table
function renderSitesTable() {
  const tbody = document.getElementById("site-table-body");
  if (!tbody || !state.sites) return;

  const query = state.searchQuery;
  const statusFilter = state.siteFilter;
  const countryFilter = state.countryFilter;
  const isPrivileged = state.currentUser && (state.currentUser.role === "management" || state.currentUser.role === "admin");

  const filtered = state.sites.filter((s) => {
    const matchSearch = s.site_id.toLowerCase().includes(query) || s.country.toLowerCase().includes(query);
    const matchStatus = statusFilter === "ALL" || s.status === statusFilter;
    const matchCountry = countryFilter === "ALL" || s.country === countryFilter;
    return matchSearch && matchStatus && matchCountry;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="padding:2rem;">No sites matching criteria.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered
    .map((s) => {
      const isClosed = state.closedSites.has(s.site_id);
      const pillClass = isClosed ? "closed" : s.is_at_risk ? "at_risk" : "healthy";
      const statusText = isClosed ? "Closed" : s.is_at_risk ? "At-Risk" : "Healthy";
      const btnActionText = isClosed ? "Reopen" : "Close";
      const btnClass = isClosed ? "btn-secondary" : "btn-danger";

      const btnHtml = isPrivileged
        ? `<button class="${btnClass}" style="padding:0.3rem 0.6rem;font-size:0.75rem;" onclick="event.stopPropagation(); toggleSiteAction('${s.site_id}')">${btnActionText}</button>`
        : `<button class="btn-outline user-view-pill" style="padding:0.3rem 0.6rem;font-size:0.75rem;" onclick="event.stopPropagation(); showToast('⚠️ Site intervention requires Management or Admin privileges.', 'warning')">View Only</button>`;

      return `
      <tr onclick="openSiteDetailModal('${s.site_id}')" style="cursor:pointer;" title="Click to inspect site historical timeline">
        <td><strong>${s.site_id}</strong></td>
        <td>${s.country}</td>
        <td>${s.hospital_tier}</td>
        <td><strong>${s.enrolled_to_date}</strong></td>
        <td>${s.posterior_mean_rate} <span style="color:var(--text-muted);font-size:0.75rem;">[${s.rate_ci_80[0]} - ${s.rate_ci_80[1]}]</span></td>
        <td style="color:${s.p_at_risk > 0.8 ? "var(--accent-red)" : "inherit"}; font-weight:${s.p_at_risk > 0.8 ? "700" : "400"};">${Math.round(s.p_at_risk * 100)}%</td>
        <td><span class="status-pill ${pillClass}">${statusText}</span></td>
        <td>${btnHtml}</td>
      </tr>
    `;
    })
    .join("");
}

// Toggle Site Open/Close
function toggleSiteAction(siteId) {
  const isPrivileged = state.currentUser && (state.currentUser.role === "management" || state.currentUser.role === "admin");
  if (!isPrivileged) {
    showToast("⚠️ Site intervention requires Management or Admin privileges.", "warning");
    return;
  }
  if (state.closedSites.has(siteId)) {
    state.closedSites.delete(siteId);
    showToast(`Site ${siteId} reopened. Recalculating forecast...`);
  } else {
    state.closedSites.add(siteId);
    showToast(`Site ${siteId} marked closed. Recalculating forecast...`);
  }
  triggerForecast();
}

// Site Detail Inspection Modal
async function openSiteDetailModal(siteId) {
  state.selectedSiteId = siteId;
  const modal = document.getElementById("site-detail-modal");
  if (!modal) return;

  const siteIdElem = document.getElementById("modal-site-id");
  const siteTitle = document.getElementById("modal-site-title");
  const siteMeta = document.getElementById("modal-site-meta");
  const enrolledElem = document.getElementById("modal-site-enrolled");
  const w40Elem = document.getElementById("modal-site-w40");
  const activeElem = document.getElementById("modal-site-active");
  const activationElem = document.getElementById("modal-site-activation");
  const toggleBtn = document.getElementById("btn-modal-toggle-site");

  if (siteIdElem) siteIdElem.textContent = siteId;
  if (siteTitle) siteTitle.textContent = `Site Performance & History (${siteId})`;

  modal.style.display = "flex";

  try {
    const res = await fetch(`/api/sites/${siteId}`);
    if (!res.ok) throw new Error("Site details not found.");
    const data = await res.json();

    if (siteMeta) siteMeta.textContent = `${data.country} • ${data.hospital_tier}`;
    if (enrolledElem) enrolledElem.textContent = data.total_enrolled.toLocaleString();
    if (w40Elem) w40Elem.textContent = data.enrolled_at_current_week.toLocaleString();
    if (activeElem) activeElem.textContent = `${data.active_weeks_count} / 104 wks`;
    if (activationElem) activationElem.textContent = `Week ${data.activation_week}`;

    const isClosed = state.closedSites.has(siteId);
    if (toggleBtn) {
      const isPrivileged = state.currentUser && (state.currentUser.role === "management" || state.currentUser.role === "admin");
      toggleBtn.textContent = isClosed ? "Reopen Site" : "Close Site";
      toggleBtn.className = isClosed ? "btn-secondary" : "btn-danger";
      toggleBtn.disabled = !isPrivileged;
    }

    renderSiteHistoryChart(data.history || []);
  } catch (err) {
    console.error("Error loading site details:", err);
  }
}

function closeSiteDetailModal() {
  const modal = document.getElementById("site-detail-modal");
  if (modal) modal.style.display = "none";
  state.selectedSiteId = null;
}

// Render SVG Timeline for Single Site
function renderSiteHistoryChart(history) {
  const svg = document.getElementById("site-history-svg");
  if (!svg || history.length === 0) return;

  const width = 700;
  const height = 200;
  const pad = { top: 15, right: 20, bottom: 30, left: 40 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const maxEnrolled = Math.max(...history.map((h) => h.enrolled), 5);
  const scaleX = (w) => pad.left + ((w - 1) / 103) * plotW;
  const scaleY = (e) => pad.top + plotH - (e / maxEnrolled) * plotH;
  const barW = Math.max(plotW / history.length - 1, 2);

  let svgContent = "";

  // Axis
  svgContent += `<line x1="${pad.left}" y1="${pad.top + plotH}" x2="${width - pad.right}" y2="${pad.top + plotH}" class="axis-line" />`;

  // Bars
  history.forEach((h) => {
    const x = scaleX(h.week);
    const y = scaleY(h.enrolled);
    const barHeight = pad.top + plotH - y;
    const color = h.week <= state.currentWeek ? "var(--accent-teal)" : "rgba(148, 163, 184, 0.4)";
    svgContent += `<rect x="${x}" y="${y}" width="${barW}" height="${barHeight}" fill="${color}" rx="1" />`;

    if (h.week % 20 === 0) {
      svgContent += `<text x="${x}" y="${height - 8}" text-anchor="middle" class="axis-text">W${h.week}</text>`;
    }
  });

  // Current week line
  const curX = scaleX(state.currentWeek);
  svgContent += `<line x1="${curX}" y1="${pad.top}" x2="${curX}" y2="${pad.top + plotH}" stroke="var(--line-observed)" stroke-dasharray="2,2" stroke-width="1.5" />`;

  svg.innerHTML = svgContent;
}
