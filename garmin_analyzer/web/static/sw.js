/* Service worker: caches the app shell so the icon on the home screen opens
   instantly and the UI loads even on a flaky connection. Live data (the /api
   calls) is always fetched fresh from the local server, never cached. */

const CACHE = "garmin-analyzer-v1";
const SHELL = [
  "/",
  "/static/style.css",
  "/static/charts.js",
  "/static/app.js",
  "/static/icon-192.png",
  "/static/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;

  // API + login/sync: always network, never serve stale health data
  if (url.pathname.startsWith("/api/")) return;

  // App shell: cache-first, fall back to network and update the cache
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const network = fetch(event.request)
        .then((res) => {
          if (res.ok && url.origin === self.location.origin) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(event.request, copy));
          }
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
