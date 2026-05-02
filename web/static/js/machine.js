// Machine detail page.
import {
  ackEvent,
  connectMachineWS,
  escapeHtml,
  fmt,
  getCycles,
  getDowntimeReasons,
  getEvents,
  getMachine,
  getOEE,
  getStats,
  showToast,
  tagDowntime,
} from "/web/js/api.js";
import { attachToggle } from "/web/js/theme.js";

const params = new URLSearchParams(location.search);
const machineId = params.get("id");

if (!machineId) {
  document.body.innerHTML =
    '<main><div class="empty error">Missing ?id= in URL</div></main>';
  throw new Error("missing id");
}

const $ = (id) => document.getElementById(id);
attachToggle($("theme-toggle"));

async function bootstrap() {
  await Promise.all([loadHeader(), loadOEE(), loadStatsAndGantt(), loadEvents(), loadDowntime()]);

  connectMachineWS(machineId, onWsMessage, {
    onConnect: () => $("machine-status").classList.remove("offline"),
    onDisconnect: () => $("machine-status").classList.add("offline"),
  });

  // Periodic refreshers as a safety net.
  setInterval(loadOEE, 30_000);
  setInterval(loadEvents, 30_000);
}

async function loadHeader() {
  try {
    const m = await getMachine(machineId);
    $("machine-name").textContent = m.name;
    $("machine-id").textContent = m.id;
    document.title = `${m.name} — DS Machine Analyzer`;
    setStatus(m.status);
    $("kpi-last-cycle").textContent = fmt.ms(m.last_cycle_ms);
    $("kpi-last-cycle-foot").textContent = m.last_cycle_id
      ? `cycle #${m.last_cycle_id}`
      : "no cycles yet";
    $("kpi-cycle-count").textContent = m.cycle_count ?? 0;
  } catch (err) {
    showToast(`Could not load machine: ${err.message}`);
  }
}

function setStatus(status) {
  const pill = $("machine-status");
  pill.className = `status ${status}`;
  pill.textContent = status;
}

async function loadOEE() {
  try {
    const o = await getOEE(machineId);
    $("oee-window").textContent = `${o.window_minutes} min`;
    $("oee-value").textContent = fmt.oee(o.oee);
    setOeeArc(o.oee);
    setBar("a", o.availability);
    setBar("p", o.performance);
    setBar("q", o.quality);
  } catch (err) {
    if (err.status === 409) {
      $("oee-value").textContent = "—";
      $("oee-window").textContent = "OEE disabled";
    } else {
      showToast(`OEE: ${err.message}`);
    }
  }
}

function setOeeArc(oee) {
  const arc = $("oee-arc");
  if (!arc) return;
  const C = 2 * Math.PI * 50; // ~314
  const offset = oee * C;
  arc.setAttribute("stroke-dasharray", `${offset.toFixed(2)} ${C.toFixed(2)}`);
  let color = "var(--c-oee-bad)";
  if (oee >= 0.85) color = "var(--c-oee-good)";
  else if (oee >= 0.6) color = "var(--c-oee-okay)";
  arc.style.stroke = color;
}

function setBar(suffix, ratio) {
  const fill = $(`bar-${suffix}`);
  const v = $(`val-${suffix}`);
  if (fill) fill.style.width = `${(ratio * 100).toFixed(1)}%`;
  if (v) v.textContent = fmt.pct(ratio);
}

async function loadStatsAndGantt() {
  // Stats table
  let stats = [];
  try {
    stats = await getStats(machineId);
  } catch {
    /* ignore */
  }
  renderStats(stats);
  if (stats.length) {
    const maxCv = Math.max(...stats.map((s) => s.cv_pct || 0));
    $("kpi-max-cv").textContent = `${maxCv.toFixed(1)}%`;
    const slowest = stats.reduce(
      (a, b) => (b.avg_ms > a.avg_ms ? b : a),
      stats[0]
    );
    $("kpi-bottleneck").textContent = slowest.step_name;
    $("kpi-bottleneck-foot").textContent = `${fmt.ms(slowest.avg_ms)} avg`;
  }

  // Gantt — most recent cycle
  try {
    const cycles = await getCycles(machineId, 1);
    if (cycles.length) renderGantt(cycles[0]);
  } catch {
    /* ignore */
  }
}

function renderStats(stats) {
  const tbody = $("step-stats-body");
  if (!stats.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty">No cycles yet</td></tr>';
    return;
  }
  tbody.innerHTML = stats
    .map(
      (s) => `
      <tr>
        <td>${escapeHtml(s.step_name)}</td>
        <td class="num">${fmt.ms(s.avg_ms)}</td>
        <td class="num">${fmt.ms(s.min_ms)}</td>
        <td class="num">${fmt.ms(s.max_ms)}</td>
        <td class="num" style="${(s.cv_pct || 0) >= 8 ? "color:var(--c-status-fault);font-weight:var(--fw-semibold)" : ""}">
          ${(s.cv_pct ?? 0).toFixed(2)}%
        </td>
      </tr>`
    )
    .join("");
}

function renderGantt(cycle) {
  $("gantt-cycle-id").textContent = `cycle #${cycle.cycle_id} — ${fmt.ms(cycle.total_ms)}`;
  const total = cycle.total_ms || 1;
  const bottleneck = cycle.bottleneck_step_index;
  const rows = cycle.steps
    .map((s) => {
      const w = ((s.duration_ms / total) * 100).toFixed(1);
      const isBottleneck = s.index === bottleneck ? " bottleneck" : "";
      return `
        <div class="gantt-row${isBottleneck}">
          <span class="name">${escapeHtml(s.name)}</span>
          <div class="bar" style="width:${w}%" data-ms="${fmt.ms(s.duration_ms)}"></div>
        </div>`;
    })
    .join("");
  $("gantt").innerHTML = rows;
}

async function loadEvents() {
  try {
    const events = await getEvents(machineId, { limit: 50 });
    renderEvents(events);
  } catch (err) {
    showToast(`Events: ${err.message}`);
  }
}

function renderEvents(events) {
  const tbody = $("events-body");
  $("events-meta").textContent = events.length ? `${events.length} entries` : "—";
  if (!events.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty">No events</td></tr>';
    return;
  }
  tbody.innerHTML = events
    .map(
      (e) => `
      <tr>
        <td title="${escapeHtml(e.timestamp)}">${escapeHtml(fmt.ago(e.timestamp))}</td>
        <td><span class="status ${e.severity}">${escapeHtml(e.severity)}</span></td>
        <td>${escapeHtml(e.category)}</td>
        <td>${escapeHtml(e.message)}</td>
        <td>${e.acknowledged ? "✓ ack" : `<button class="btn" data-ack="${e.id}">ack</button>`}</td>
      </tr>`
    )
    .join("");

  tbody.querySelectorAll("[data-ack]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const id = Number(btn.getAttribute("data-ack"));
      try {
        await ackEvent(machineId, id, "operator");
        showToast("Event acknowledged");
        loadEvents();
      } catch (err) {
        showToast(`Ack failed: ${err.message}`);
      }
    })
  );
}

async function loadDowntime() {
  let reasons = [];
  try {
    reasons = await getDowntimeReasons(machineId);
  } catch (err) {
    if (err.status === 409 || err.status === 404) {
      $("downtime-chips").innerHTML =
        '<div class="empty">Event log is not enabled for this machine.</div>';
      return;
    }
    showToast(`Downtime: ${err.message}`);
    return;
  }

  const wrap = $("downtime-chips");
  wrap.innerHTML = "";
  for (const r of reasons) {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = humanize(r);
    chip.title = r;
    chip.addEventListener("click", async () => {
      chip.disabled = true;
      try {
        await tagDowntime(machineId, { reason: r, by: "operator" });
        showToast(`Tagged: ${humanize(r)}`);
        loadEvents();
      } catch (err) {
        showToast(`Failed: ${err.message}`);
      } finally {
        chip.disabled = false;
      }
    });
    wrap.appendChild(chip);
  }
}

function humanize(s) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function onWsMessage(_machineId, msgOrSelf) {
  // connectMachineWS calls cb(msg) only — the second arg here exists for
  // future per-page hooks. Pull the actual msg either way.
  const msg = msgOrSelf ?? _machineId;
  if (!msg || typeof msg !== "object" || !msg.type) return;

  if (msg.type === "cycle_summary") {
    $("kpi-last-cycle").textContent = fmt.ms(msg.payload.total_ms);
    $("kpi-last-cycle-foot").textContent = `cycle #${msg.payload.cycle_id}`;
    if (msg.payload.bottleneck_step) {
      $("kpi-bottleneck").textContent = msg.payload.bottleneck_step;
      $("kpi-bottleneck-foot").textContent = `${fmt.ms(
        msg.payload.bottleneck_step_ms
      )} avg`;
    }
    if (msg.payload.max_cv_pct != null) {
      $("kpi-max-cv").textContent = `${msg.payload.max_cv_pct.toFixed(1)}%`;
    }
    if (msg.payload.steps) {
      // Reconstruct a compact cycle for the gantt
      renderGantt({
        cycle_id: msg.payload.cycle_id,
        total_ms: msg.payload.total_ms,
        bottleneck_step_index: msg.payload.bottleneck_step_index,
        steps: msg.payload.steps,
      });
    }
    // Refresh stats + OEE in the background (server-of-truth).
    loadStatsAndGantt();
    loadOEE();
  } else if (msg.type === "status_change") {
    if (msg.payload.status) setStatus(msg.payload.status);
  } else if (msg.type === "cycle_anomaly") {
    showToast(
      `Anomaly: ${msg.payload.step_name} CV%=${msg.payload.cv_pct.toFixed(1)}`
    );
    loadEvents();
  } else if (msg.type === "alarm") {
    showToast(`Alarm: ${msg.payload.message ?? msg.payload.code}`);
    loadEvents();
  }
}

// connectMachineWS gives us callback(msg) — adapt to keep onWsMessage's arity flexible.
const _origConnect = connectMachineWS;
// (no behavior change needed; we re-import above already)

bootstrap();
