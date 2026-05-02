// DS Machine Analyzer — Service Worker
// Handles: offline cache, push notifications, background sync.
//
// Strategy:
//   - Static assets (CSS/JS/icons): cache-first
//   - API responses: network-first with stale-while-revalidate fallback
//   - WebSocket events: never cached, always live

const CACHE_VERSION = "ds-ma-v0.1.1";
const STATIC_CACHE = `static-${CACHE_VERSION}`;

const STATIC_ASSETS = [
  "/web/",
  "/web/index.html",
  "/web/machine.html",
  "/web/manifest.json",
  "/web/css/tokens.css",
  "/web/css/style.css",
  "/web/js/api.js",
  "/web/js/theme.js",
  "/web/js/index.js",
  "/web/js/machine.js",
  "/web/icons/icon.svg",
  "/web/icons/icon-192.png",
  "/web/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== STATIC_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  if (STATIC_ASSETS.some((p) => url.pathname.endsWith(p.replace("/web/", "")))) {
    event.respondWith(cacheFirst(event.request));
    return;
  }
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  return cached || fetch(request);
}

async function networkFirst(request) {
  try {
    const fresh = await fetch(request);
    return fresh;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(JSON.stringify({ error: "offline" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

// Push notifications — alarm / NG events from backend
self.addEventListener("push", (event) => {
  if (!event.data) return;
  const data = event.data.json();
  event.waitUntil(
    self.registration.showNotification(data.title || "DS Machine Analyzer", {
      body: data.body,
      icon: "/web/icons/icon-192.png",
      badge: "/web/icons/icon-192.png",
      data: { url: data.url || "/web/" },
      tag: data.tag,
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow(event.notification.data.url));
});
