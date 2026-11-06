/**
 * Clinical Trial Enrollment Forecasting Dashboard
 * Reactive UI with Inline SVG Fan Chart, Histogram, What-If Simulation Sandbox,
 * and Site Intervention Management.
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
  searchQuery: "",
  theme: localStorage.getItem("ct_theme") || "dark",
  forecastData: null,
  baselineData: null,
  sites: [],
};

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initEventListeners();
  checkHealth();
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

  document.getElementById("btn-close-at-risk")?.addEventListener("click", () => {
    if (!state.forecastData) return;
    state.forecastData.sites.forEach((s) => {
      if (s.is_at_risk) {
        state.closedSites.add(s.site_id);
      }
    });
    triggerForecast();
  });

  document.getElementById("btn-reset")?.addEventListener("click", () => {
    state.flowChange = 0.0;
    state.newSites = 0;
    state.closedSites.clear();
    document.getElementById("slider-flow").value = "0";
    document.getElementById("flow-val").textContent = "+0%";
    document.getElementById("slider-new-sites").value = "0";
    document.getElementById("new-sites-val").textContent = "0 sites";
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
    updateScenarioBadge(data);
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

// Render Inline SVG Fan Chart
function renderFanChart(data) {
  const svg = document.getElementById("fan-chart-svg");
  if (!svg) return;

  const width = 850;
  const height = 360;
  const pad = { top: 30, right: 40, bottom: 45, left: 65 };

  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const hist = data.observed_history;
  const fan = data.forecast_fan;

  const minWeek = 1;
  const maxWeek = 104;

  const maxEnroll = Math.max(
    data.target * 1.25,
    Math.max(...fan.q975),
    hist.length > 0 ? hist[hist.length - 1].cumulative_enrolled : 0
  );

  const scaleX = (w) => pad.left + ((w - minWeek) / (maxWeek - minWeek)) * plotW;
  const scaleY = (v) => pad.top + plotH - (v / maxEnroll) * plotH;

  let svgContent = "";

  // 1. Grid Lines
  for (let w = 10; w <= 100; w += 10) {
    const x = scaleX(w);
    svgContent += `<line x1="${x}" y1="${pad.top}" x2="${x}" y2="${pad.top + plotH}" class="grid-line" />`;
    svgContent += `<text x="${x}" y="${height - 15}" text-anchor="middle" class="axis-text">${w}w</text>`;
  }

  for (let val = 0; val <= maxEnroll; val += 300) {
    const y = scaleY(val);
    svgContent += `<line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}" class="grid-line" />`;
    svgContent += `<text x="${pad.left - 10}" y="${y + 4}" text-anchor="end" class="axis-text">${val}</text>`;
  }

  // 2. Target Line & Deadline Line
  const targetY = scaleY(data.target);
  svgContent += `<line x1="${pad.left}" y1="${targetY}" x2="${width - pad.right}" y2="${targetY}" stroke="var(--line-target)" stroke-width="1.8" stroke-dasharray="5,5" />`;
  svgContent += `<text x="${width - pad.right - 10}" y="${targetY - 8}" text-anchor="end" fill="var(--line-target)" font-size="11" font-weight="600">Target (${data.target})</text>`;

  const deadlineX = scaleX(data.deadline);
  svgContent += `<line x1="${deadlineX}" y1="${pad.top}" x2="${deadlineX}" y2="${pad.top + plotH}" stroke="var(--line-deadline)" stroke-width="1.8" stroke-dasharray="3,3" />`;
  svgContent += `<text x="${deadlineX + 5}" y="${pad.top + 15}" fill="var(--line-deadline)" font-size="11" font-weight="600">Deadline (W${data.deadline})</text>`;

  // 3. Credible Bands (95% & 80%)
  const weeks = fan.weeks;
  if (weeks.length > 0) {
    // 95% Band Polygon
    let poly95 = "";
    for (let i = 0; i < weeks.length; i++) {
      poly95 += `${scaleX(weeks[i])},${scaleY(fan.q975[i])} `;
    }
    for (let i = weeks.length - 1; i >= 0; i--) {
      poly95 += `${scaleX(weeks[i])},${scaleY(fan.q025[i])} `;
    }
    svgContent += `<polygon points="${poly95}" fill="var(--band-95)" />`;

    // 80% Band Polygon
    let poly80 = "";
    for (let i = 0; i < weeks.length; i++) {
      poly80 += `${scaleX(weeks[i])},${scaleY(fan.q90[i])} `;
    }
    for (let i = weeks.length - 1; i >= 0; i--) {
      poly80 += `${scaleX(weeks[i])},${scaleY(fan.q10[i])} `;
    }
    svgContent += `<polygon points="${poly80}" fill="var(--band-80)" />`;

    // Median Forecast Line (q50)
    let path50 = `M ${scaleX(data.current_week)},${scaleY(data.total_enrolled_to_date)} `;
    for (let i = 0; i < weeks.length; i++) {
      path50 += `L ${scaleX(weeks[i])},${scaleY(fan.q50[i])} `;
    }
    svgContent += `<path d="${path50}" fill="none" stroke="var(--line-median)" stroke-width="2.2" stroke-dasharray="6,4" />`;
  }

  // 4. Observed Trajectory Line
  if (hist.length > 0) {
    let pathObs = `M ${scaleX(hist[0].week)},${scaleY(hist[0].cumulative_enrolled)} `;
    for (let i = 1; i < hist.length; i++) {
      pathObs += `L ${scaleX(hist[i].week)},${scaleY(hist[i].cumulative_enrolled)} `;
    }
    svgContent += `<path d="${pathObs}" fill="none" stroke="var(--line-observed)" stroke-width="2.6" />`;
  }

  // 5. Current Origin Node
  const curX = scaleX(data.current_week);
  const curY = scaleY(data.total_enrolled_to_date);
  svgContent += `<circle cx="${curX}" cy="${curY}" r="5" fill="var(--accent-blue)" stroke="white" stroke-width="2" />`;

  svg.innerHTML = svgContent;
}

// Render Completion Week Histogram
function renderHistogram(data) {
  const svg = document.getElementById("hist-chart-svg");
  if (!svg) return;

  const width = 450;
  const height = 360;
  const pad = { top: 30, right: 30, bottom: 45, left: 45 };

  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const bins = data.completion_histogram;
  if (!bins || bins.length === 0) return;

  const maxCount = Math.max(...bins.map((b) => b.count), 1);
  const minW = bins[0].week;
  const maxW = bins[bins.length - 1].week + 2;

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
  const filter = state.siteFilter;

  const filtered = state.sites.filter((s) => {
    const matchSearch = s.site_id.toLowerCase().includes(query) || s.country.toLowerCase().includes(query);
    const matchFilter = filter === "ALL" || s.status === filter;
    return matchSearch && matchFilter;
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

      return `
      <tr onclick="toggleSiteAction('${s.site_id}')">
        <td><strong>${s.site_id}</strong></td>
        <td>${s.country}</td>
        <td>${s.hospital_tier}</td>
        <td><strong>${s.enrolled_to_date}</strong></td>
        <td>${s.posterior_mean_rate} <span style="color:var(--text-muted);font-size:0.75rem;">[${s.rate_ci_80[0]} - ${s.rate_ci_80[1]}]</span></td>
        <td style="color:${s.p_at_risk > 0.8 ? "var(--accent-red)" : "inherit"}; font-weight:${s.p_at_risk > 0.8 ? "700" : "400"};">${Math.round(s.p_at_risk * 100)}%</td>
        <td><span class="status-pill ${pillClass}">${statusText}</span></td>
        <td><button class="${btnClass}" style="padding:0.3rem 0.6rem;font-size:0.75rem;" onclick="event.stopPropagation(); toggleSiteAction('${s.site_id}')">${btnActionText}</button></td>
      </tr>
    `;
    })
    .join("");
}

// Toggle Site Open/Close
function toggleSiteAction(siteId) {
  if (state.closedSites.has(siteId)) {
    state.closedSites.delete(siteId);
  } else {
    state.closedSites.add(siteId);
  }
  triggerForecast();
}

