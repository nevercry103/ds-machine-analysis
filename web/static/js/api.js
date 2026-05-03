// Shared API client — wraps fetch + WebSocket against the same backend
// the PyQt6 desktop uses. All pages import from this module.

const BASE = "/api";

async function jsonRequest(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await resp.text();
  let body;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!resp.ok) {
    const msg = body && body.detail ? body.detail : `HTTP ${resp.status}`;
    throw new ApiError(msg, resp.status, body);
  }
  return body;
}

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

// Health
export const getHealth = () => jsonRequest("/health");
export const getLicense = () => jsonRequest("/license");

// Machines
export const listMachines = () => jsonRequest("/machines");
export const getMachine = (id) => jsonRequest(`/machines/${encodeURIComponent(id)}`);
export const getCycles = (id, limit = 100) =>
  jsonRequest(`/machines/${encodeURIComponent(id)}/cycles?limit=${limit}`);
export const getStats = (id) =>
  jsonRequest(`/machines/${encodeURIComponent(id)}/stats`);
export const getOEE = (id) =>
  jsonRequest(`/machines/${encodeURIComponent(id)}/oee`);
export const getEvents = (id, opts = {}) => {
  const q = new URLSearchParams();
  q.set("limit", opts.limit ?? 100);
  if (opts.severity) q.set("severity", opts.severity);
  if (opts.category) q.set("category", opts.category);
  return jsonRequest(`/machines/${encodeURIComponent(id)}/events?${q}`);
};
export const ackEvent = (id, eventId, by) =>
  jsonRequest(`/machines/${encodeURIComponent(id)}/events/${eventId}/ack`, {
    method: "POST",
    body: JSON.stringify({ acknowledged_by: by }),
  });
export const tagDowntime = (id, payload) =>
  jsonRequest(`/machines/${encodeURIComponent(id)}/downtime`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
export const getDowntimeReasons = (id) =>
  jsonRequest(`/machines/${encodeURIComponent(id)}/downtime/reasons`);

// Packs
export const listPacks = () => jsonRequest("/packs");

// Logbook (F-006)
export const getLogbook = (id, opts = {}) => {
  const q = new URLSearchParams();
  q.set("limit", opts.limit ?? 50);
  if (opts.entry_type) q.set("entry_type", opts.entry_type);
  return jsonRequest(`/machines/${encodeURIComponent(id)}/logbook?${q}`);
};
export const createLogbookEntry = (id, payload) =>
  jsonRequest(`/machines/${encodeURIComponent(id)}/logbook`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

// =====================================================================
// WebSocket — auto-reconnecting, JSON frames only.
// =====================================================================
export function connectMachineWS(machineId, onMessage, opts = {}) {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${proto}//${window.location.host}/ws/machines/${encodeURIComponent(
    machineId
  )}/events`;

  let ws = null;
  let stopped = false;
  let backoffMs = 500;
  const maxBackoff = 10_000;

  function open() {
    ws = new WebSocket(url);
    ws.addEventListener("open", () => {
      backoffMs = 500;
      opts.onConnect?.();
    });
    ws.addEventListener("message", (event) => {
      try {
        onMessage(JSON.parse(event.data));
      } catch (err) {
        console.warn("WS message not JSON:", err);
      }
    });
    ws.addEventListener("close", () => {
      opts.onDisconnect?.();
      if (stopped) return;
      setTimeout(open, backoffMs);
      backoffMs = Math.min(maxBackoff, backoffMs * 2);
    });
    ws.addEventListener("error", () => {
      // close handler handles reconnect
    });
  }

  open();

  return {
    close() {
      stopped = true;
      if (ws) ws.close();
    },
  };
}

// =====================================================================
// Tiny formatting helpers
// =====================================================================
export const fmt = {
  ms(ms) {
    if (ms == null) return "—";
    if (ms < 1000) return `${Math.round(ms)} ms`;
    if (ms < 60_000) return `${(ms / 1000).toFixed(2)} s`;
    return `${(ms / 60_000).toFixed(1)} min`;
  },
  pct(ratio) {
    if (ratio == null) return "—";
    return `${(ratio * 100).toFixed(1)}%`;
  },
  oee(ratio) {
    if (ratio == null) return "—";
    return `${(ratio * 100).toFixed(0)}%`;
  },
  ts(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleString();
    } catch {
      return iso;
    }
  },
  ago(iso) {
    if (!iso) return "—";
    const then = new Date(iso).getTime();
    const diff = Math.max(0, Date.now() - then);
    if (diff < 60_000) return `${Math.round(diff / 1000)}s ago`;
    if (diff < 3_600_000) return `${Math.round(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.round(diff / 3_600_000)}h ago`;
    return new Date(iso).toLocaleDateString();
  },
};

export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

export function showToast(message, ms = 2200) {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), ms);
}
