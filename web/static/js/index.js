// Machine list page bootstrap.
import {
  ApiError,
  connectMachineWS,
  escapeHtml,
  fmt,
  getHealth,
  getLicense,
  listMachines,
  getStats,
} from "/web/js/api.js";
import { attachToggle } from "/web/js/theme.js";

const grid = document.getElementById("grid");
const machineCountLabel = document.getElementById("machine-count");
const lastUpdated = document.getElementById("last-updated");
const connectionPill = document.getElementById("connection");
const tierPill = document.getElementById("tier");

attachToggle(document.getElementById("theme-toggle"));
wireInstallPrompt(document.getElementById("install-app"));

// PWA install — Chromium fires `beforeinstallprompt` when criteria are
// met (HTTPS or localhost, manifest valid, SW registered). We surface the
// header button only then; iOS Safari users still get the standard
// "Add to Home Screen" path via the share sheet.
function wireInstallPrompt(button) {
  if (!button) return;
  let deferred = null;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferred = e;
    button.hidden = false;
  });
  button.addEventListener("click", async () => {
    if (!deferred) return;
    deferred.prompt();
    await deferred.userChoice;
    deferred = null;
    button.hidden = true;
  });
  window.addEventListener("appinstalled", () => {
    button.hidden = true;
  });
}

/** Map machine_id -> {card element, last sparkline values} */
const cards = new Map();

async function bootstrap() {
  // Health badge
  try {
    await getHealth();
    connectionPill.textContent = "online";
    connectionPill.classList.add("status", "online");
  } catch {
    connectionPill.textContent = "offline";
    connectionPill.classList.add("status", "fault");
  }

  // License badge
  try {
    const lic = await getLicense();
    tierPill.textContent = lic.tier_id || "dev";
    tierPill.title = lic.display_name || "Unlicensed dev mode";
  } catch {
    tierPill.textContent = "?";
  }

  // Machine list
  await refreshMachines();
  setInterval(refreshMachines, 15_000); // safety net poll

  // For each machine, also subscribe to its WS for instant updates
  for (const id of cards.keys()) {
    connectMachineWS(id, (msg) => onWsMessage(id, msg));
  }
}

async function refreshMachines() {
  let machines;
  try {
    machines = await listMachines();
  } catch (err) {
    grid.innerHTML = `<div class="empty error">Cannot reach API: ${escapeHtml(
      err.message
    )}</div>`;
    machineCountLabel.textContent = "Machines";
    return;
  }

  if (!machines.length) {
    grid.innerHTML = `<div class="empty">No machines configured yet. Drop a YAML in <code>config/machines/</code> and restart.</div>`;
    machineCountLabel.textContent = "Machines (0)";
    return;
  }

  grid.innerHTML = "";
  cards.clear();
  machineCountLabel.textContent = `Machines (${machines.length})`;
  lastUpdated.textContent = `Updated ${fmt.ts(new Date().toISOString())}`;

  for (const m of machines) {
    const card = document.createElement("a");
    card.href = `/web/machine.html?id=${encodeURIComponent(m.id)}`;
    card.className = `machine-card ${m.status}`;
    card.dataset.id = m.id;
    card.innerHTML = renderCardBody(m);
    grid.appendChild(card);
    cards.set(m.id, { card, samples: [] });
    populateSpark(m.id).catch(() => {});
  }
}

function renderCardBody(m) {
  return `
    <div class="meta">
      <span class="status ${m.status}">${escapeHtml(m.status)}</span>
      <span class="ms">cycle #${m.last_cycle_id ?? "—"}</span>
    </div>
    <h2 class="name">${escapeHtml(m.name)}</h2>
    <div class="meta">
      <span class="ms">last: ${fmt.ms(m.last_cycle_ms)}</span>
      <span class="ms">${m.cycle_count} cycles</span>
    </div>
    <svg class="spark" viewBox="0 0 100 32" preserveAspectRatio="none">
      <path class="area" d=""></path>
      <path class="line" d=""></path>
    </svg>
  `;
}

async function populateSpark(machineId) {
  // Use last 30 cycles of step-stats avg as a proxy if we can; otherwise
  // last 30 cycles' total_ms.
  const entry = cards.get(machineId);
  if (!entry) return;
  // For simplicity, fetch /stats and use the average across all step
  // averages so the sparkline reflects rolling tempo.
  try {
    const stats = await getStats(machineId);
    if (!stats || !stats.length) return;
    // Sparkline shows the per-step average — sorted by step index.
    const samples = stats.map((s) => s.avg_ms);
    entry.samples = samples;
    drawSpark(entry.card.querySelector(".spark"), samples);
  } catch {
    /* ignore */
  }
}

function drawSpark(svg, values) {
  if (!svg || !values.length) return;
  const W = 100;
  const H = 32;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = values.length === 1 ? W : W / (values.length - 1);
  const points = values.map((v, i) => {
    const x = i * step;
    const y = H - ((v - min) / range) * (H - 4) - 2;
    return [x, y];
  });
  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)},${p[1].toFixed(1)}`)
    .join("");
  const areaPath =
    `M${points[0][0].toFixed(1)},${H} L` +
    points.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" L") +
    ` L${points[points.length - 1][0].toFixed(1)},${H} Z`;

  svg.querySelector(".line").setAttribute("d", linePath);
  svg.querySelector(".area").setAttribute("d", areaPath);
}

function onWsMessage(machineId, msg) {
  const entry = cards.get(machineId);
  if (!entry) return;

  if (msg.type === "cycle_summary") {
    const card = entry.card;
    const total = msg.payload.total_ms;
    card.querySelector(".meta:last-of-type .ms:first-child").textContent =
      `last: ${fmt.ms(total)}`;
    // push to sparkline (rolling 30)
    entry.samples.push(total);
    if (entry.samples.length > 30) entry.samples.shift();
    drawSpark(card.querySelector(".spark"), entry.samples);
    lastUpdated.textContent = `Updated ${fmt.ts(new Date().toISOString())}`;
  } else if (msg.type === "status_change") {
    const card = entry.card;
    const newStatus = msg.payload.status;
    if (newStatus) {
      card.className = `machine-card ${newStatus}`;
      const pill = card.querySelector(".status");
      pill.className = `status ${newStatus}`;
      pill.textContent = newStatus;
    }
  } else if (msg.type === "cycle_anomaly") {
    // Visual hint — pulse the card border.
    entry.card.style.borderLeftColor = "var(--c-status-fault)";
    setTimeout(() => {
      entry.card.style.borderLeftColor = "";
    }, 2000);
  }
}

bootstrap();
