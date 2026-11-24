/* Pass-through no-op ServiceWorker (never unregisters host/proxy ServiceWorkers such as scf.usercontent.goog) */
self.addEventListener("install", () => {
  self.skipWaiting();
});
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});
