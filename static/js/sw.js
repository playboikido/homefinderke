const CACHE_NAME = 'homefinderke-cache-v1';
const OFFLINE_URL = '/offline/';

const PRECACHE_URLS = [
  '/static/css/style.css',
  OFFLINE_URL,
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;

  // Only handle GET requests
  if (req.method !== 'GET') return;

  // Static files: cache-first
  if (req.url.includes('/static/') || req.url.includes('/media/')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        return cached || fetch(req).then((res) => {
          const resClone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, resClone));
          return res;
        });
      })
    );
    return;
  }

 // Page navigations: network-first, never serve stale cached HTML —
// only fall back to a dedicated offline page if the network genuinely fails
if (req.mode === 'navigate') {
  event.respondWith(
    fetch(req).catch(() => caches.match(OFFLINE_URL))
  );
}
});