/* Dashboard logic: tabs, data loading, rendering. */

const api = (path) => fetch(path).then((r) => r.json());
const post = (path, body) =>
  fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }).then(async (r) => ({ ok: r.ok, data: await r.json() }));

let rangeDays = 30;
let granularity = "week";

/* ------------------------------- tabs ---------------------------------- */
document.getElementById("tabs").addEventListener("click", (ev) => {
  const btn = ev.target.closest(".tab");
  if (!btn) return;
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
  btn.classList.add("active");
  document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  if (btn.dataset.tab === "charts") loadCharts();
  if (btn.dataset.tab === "trends") loadTrends();
  if (btn.dataset.tab === "correlations") loadCorrelations();
});

/* ------------------------------ status --------------------------------- */
async function loadStatus() {
  const s = await api("/api/status");
  const chip = document.getElementById("status-chip");
  const parts = [];
  if (s.demo) parts.push("מצב דמו");
  parts.push(s.days ? `${s.days} ימים במסד` : "אין נתונים עדיין");
  if (s.latest) parts.push(`עדכני ל-${s.latest}`);
  parts.push(s.logged_in ? "מחובר לגרמין ✓" : "לא מחובר");
  chip.textContent = parts.join(" · ");
  return s;
}

/* ------------------------------- today --------------------------------- */
const STATUS_ICON = { ready: "🟢", moderate: "🟡", rest: "🔴", no_data: "⚪" };
const SENT_ICON = { good: "✓", warn: "!", bad: "✗" };

function fmtHours(sec) {
  if (sec == null) return "–";
  const h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60);
  return `${h}:${String(m).padStart(2, "0")}`;
}
const fmtTime = (iso) => (iso ? iso.slice(11, 16) : "–");

function kpi(label, value, unit, base) {
  return `<div class="kpi"><div class="k-label">${label}</div>
    <div class="k-value">${value ?? "–"}<span class="k-unit"> ${unit || ""}</span></div>
    ${base ? `<div class="k-base">${base}</div>` : ""}</div>`;
}

async function loadToday() {
  const { insight, day } = await api("/api/today");
  const card = document.getElementById("insight-card");
  if (!insight) {
    card.innerHTML = `<p class="empty-note">אין נתונים עדיין - עבור ללשונית "סנכרון" כדי להתחבר לגרמין ולמשוך נתונים.</p>`;
    return;
  }
  const statusClass = { ready: "status-ready", moderate: "status-moderate", rest: "status-rest" }[insight.status] || "";
  card.innerHTML = `
    <div class="insight-head">
      <span style="font-size:34px">${STATUS_ICON[insight.status] || ""}</span>
      <div>
        <div class="insight-title ${statusClass}">${insight.title}</div>
        <div class="insight-date">בוקר ${insight.date}${insight.score != null ? ` · ציון התאוששות ${insight.score}/100` : ""}</div>
      </div>
    </div>
    <p class="insight-reco">${insight.recommendation}</p>
    <ul class="findings">
      ${insight.findings.map((f) => `<li><span class="dot ${f.sentiment}"></span><span class="sent-icon">${SENT_ICON[f.sentiment] || ""}</span><span>${f.text}</span></li>`).join("")}
    </ul>`;

  if (day) {
    const b = insight.baselines || {};
    const baseStr = (key, unit) => b[key] ? `בסיס אישי: ${b[key].mean}${unit || ""}` : "";
    document.getElementById("today-kpis").innerHTML =
      kpi("Sleep Score", day.sleep_score, "", `${fmtHours(day.sleep_duration_sec)} שעות שינה`) +
      kpi("HRV", day.hrv_last_night != null ? Math.round(day.hrv_last_night) : null, "ms",
          insight.hrv_balanced_range ? `טווח מאוזן: ${insight.hrv_balanced_range[0]}–${insight.hrv_balanced_range[1]}` : baseStr("hrv_last_night", "ms")) +
      kpi("Resting HR", day.resting_hr, "bpm", baseStr("resting_hr")) +
      kpi("דופק בשינה", day.sleep_avg_hr != null ? Math.round(day.sleep_avg_hr) : null, "bpm", baseStr("sleep_avg_hr")) +
      kpi("Body Battery", day.bb_high != null ? `${day.bb_low ?? "?"}–${day.bb_high}` : null, "",
          day.bb_charged != null ? `נטען +${day.bb_charged} בלילה` : "") +
      kpi("Stress", day.stress_avg, "", day.stress_max != null ? `שיא: ${day.stress_max}` : "") +
      kpi("שינה", `<span dir="ltr" class="k-time">${fmtTime(day.bedtime)} → ${fmtTime(day.wake_time)}</span>`, "", "הרדמות → יקיצה") +
      kpi("צעדים", day.steps != null ? day.steps.toLocaleString() : null, "", "");
  }
}

/* ------------------------------- charts -------------------------------- */
document.getElementById("range-filter").addEventListener("click", (ev) => {
  const chipEl = ev.target.closest(".chip");
  if (!chipEl) return;
  document.querySelectorAll("#range-filter .chip").forEach((c) => c.classList.remove("active"));
  chipEl.classList.add("active");
  rangeDays = +chipEl.dataset.days;
  loadCharts();
});

async function loadCharts() {
  const { rows } = await api(`/api/history?days=${rangeDays}`);
  const hr = (sec) => (sec != null ? +(sec / 3600).toFixed(2) : null);
  const stageData = rows.map((r) => ({
    date: r.date,
    deep: hr(r.deep_sec), light: hr(r.light_sec), rem: hr(r.rem_sec), awake: hr(r.awake_sec),
  }));
  Charts.stackedBar(document.getElementById("chart-sleep-stages"), {
    data: stageData,
    series: [
      { key: "deep", label: "Deep", colorVar: "--series-1" },
      { key: "light", label: "Light", colorVar: "--series-2" },
      { key: "rem", label: "REM", colorVar: "--series-3" },
      { key: "awake", label: "Awake", colorVar: "--series-4" },
    ],
    valueFmt: (v) => `${Math.floor(v)}:${String(Math.round((v % 1) * 60)).padStart(2, "0")}`,
  });

  Charts.line(document.getElementById("chart-sleep-score"), {
    data: rows, series: [{ key: "sleep_score", label: "Score", colorVar: "--series-1" }],
  });

  Charts.line(document.getElementById("chart-hrv"), {
    data: rows,
    series: [{ key: "hrv_last_night", label: "HRV", colorVar: "--series-1" }],
    band: { lowKey: "hrv_balanced_low", highKey: "hrv_balanced_high" },
    valueFmt: (v) => `${Math.round(v)}ms`,
  });

  Charts.line(document.getElementById("chart-hr"), {
    data: rows,
    series: [
      { key: "resting_hr", label: "Resting", colorVar: "--series-1" },
      { key: "sleep_avg_hr", label: "Sleep", colorVar: "--series-2" },
      { key: "day_active_avg_hr", label: "Day", colorVar: "--series-3" },
    ],
    valueFmt: (v) => `${Math.round(v)} bpm`,
  });

  Charts.divergingBar(document.getElementById("chart-bb"), {
    data: rows, upKey: "bb_charged", downKey: "bb_drained",
    upLabel: "טעינה בלילה", downLabel: "ריקון ביום",
  });

  Charts.line(document.getElementById("chart-stress"), {
    data: rows, series: [{ key: "stress_avg", label: "Stress", colorVar: "--series-1" }],
  });
}

/* ------------------------------- trends -------------------------------- */
document.getElementById("gran-filter").addEventListener("click", (ev) => {
  const chipEl = ev.target.closest(".chip");
  if (!chipEl) return;
  document.querySelectorAll("#gran-filter .chip").forEach((c) => c.classList.remove("active"));
  chipEl.classList.add("active");
  granularity = chipEl.dataset.gran;
  loadTrends();
});

/* [key, label, formatter, isHigherBetter] - null direction = neutral gray */
const TREND_COLS = [
  ["sleep_score", "Sleep Score", null, true],
  ["sleep_duration_sec", "שינה (שעות)", (v) => (v / 3600).toFixed(1), true],
  ["hrv_last_night", "HRV (ms)", null, true],
  ["resting_hr", "RHR", null, false],
  ["sleep_avg_hr", "Sleep HR", null, false],
  ["stress_avg", "Stress", null, false],
  ["bb_charged", "BB טעינה", null, true],
  ["steps", "צעדים", (v) => Math.round(v).toLocaleString(), null],
];

async function loadTrends() {
  const t = await api(`/api/trends?granularity=${granularity}`);
  const summary = document.getElementById("trend-summary");
  if (t.summary && t.summary.length) {
    summary.classList.remove("hidden");
    summary.innerHTML = `<h3>מה השתנה לאחרונה</h3><ul class="summary-lines">` +
      t.summary.map((s) => `<li>${s}</li>`).join("") + "</ul>";
  } else {
    summary.classList.add("hidden");
  }

  const table = document.getElementById("trend-table");
  const periods = [...t.periods].reverse();
  table.innerHTML =
    "<tr><th>תקופה</th><th>ימים</th>" +
    TREND_COLS.map(([, label]) => `<th>${label}</th>`).join("") + "</tr>" +
    periods.map((p) => {
      const cells = TREND_COLS.map(([key, , fmt, higherBetter]) => {
        let v = p[key];
        if (v == null) return "<td class='num'>–</td>";
        const d = p.deltas && p.deltas[key];
        let deltaHtml = "";
        if (d != null && Math.abs(d) >= 1) {
          // color reflects whether the change is good for THIS metric
          const cls = higherBetter == null ? "delta-flat" :
            (d > 0) === higherBetter ? "delta-up" : "delta-down";
          deltaHtml = `<span class="${cls}"> ${d > 0 ? "▲" : "▼"}${Math.abs(d).toFixed(0)}%</span>`;
        }
        return `<td class="num">${fmt ? fmt(v) : v}${deltaHtml}</td>`;
      }).join("");
      return `<tr><td>${p.period}</td><td class="num">${p.days}</td>${cells}</tr>`;
    }).join("");
}

/* ---------------------------- correlations ------------------------------ */
async function loadCorrelations() {
  const { correlations } = await api("/api/correlations");
  const box = document.getElementById("correlations-list");
  if (!correlations.length) {
    box.innerHTML = `<p class="empty-note">עדיין אין מספיק נתונים לזיהוי קשרים מובהקים - נסה אחרי שבועיים של סנכרון.</p>`;
    return;
  }
  box.innerHTML = correlations.map((c) => `
    <div class="corr">
      <div class="corr-head">
        <span class="corr-title">${c.pair}</span>
        <span class="corr-badge">קשר ${c.strength} ${c.direction === "positive" ? "חיובי" : "שלילי"}</span>
        <span class="corr-meta">r=${c.r} · n=${c.n}</span>
      </div>
      <p class="corr-text">${c.text}</p>
    </div>`).join("");
}

/* ----------------------------- sync/login ------------------------------- */
let pollTimer = null;

function poll() {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(async () => {
    const s = await loadStatus();
    const syncStatus = document.getElementById("sync-status");
    const loginStatus = document.getElementById("login-status");
    const mfaRow = document.getElementById("mfa-row");

    syncStatus.textContent = s.sync.message || "";
    document.getElementById("sync-btn").disabled = s.sync.state === "running";

    loginStatus.textContent = s.login.message || "";
    mfaRow.classList.toggle("hidden", s.login.state !== "mfa_required");
    document.getElementById("login-btn").disabled =
      s.login.state === "running" || s.login.state === "mfa_required";

    const busy = s.sync.state === "running" ||
      s.login.state === "running" || s.login.state === "mfa_required";
    if (s.sync.state === "done") loadToday();
    if (busy) poll();
  }, 1200);
}

document.getElementById("sync-btn").addEventListener("click", async () => {
  const days = +document.getElementById("sync-days").value;
  const res = await post("/api/sync", { days });
  document.getElementById("sync-status").textContent =
    res.ok ? "הסנכרון התחיל..." : res.data.error || "שגיאה";
  if (res.ok) poll();
});

document.getElementById("login-btn").addEventListener("click", async () => {
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  if (!email || !password) {
    document.getElementById("login-status").textContent = "נא למלא אימייל וסיסמה";
    return;
  }
  const res = await post("/api/login", { email, password });
  document.getElementById("login-status").textContent =
    res.ok ? "מתחבר..." : res.data.error || "שגיאה";
  if (res.ok) poll();
});

document.getElementById("mfa-btn").addEventListener("click", async () => {
  const code = document.getElementById("mfa-code").value.trim();
  if (!code) return;
  await post("/api/login/mfa", { code });
  poll();
});

/* -------------------------------- init ---------------------------------- */
loadStatus();
loadToday();
