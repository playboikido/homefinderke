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

  // Page navigations: network-first, fall back to cache, then offline page
  if (req.mode === 'navigate') {
    const url = new URL(req.url);
    // Let the browser handle third-party/cross-origin requests, authentication flows, and admin pages normally.
    if (url.origin !== self.location.origin || 
        url.pathname.startsWith('/accounts/') || 
        url.pathname.startsWith('/control-panel-2947/')) {
      return;
    }
    event.respondWith(
      fetch(req)
        .then((res) => {
          const resClone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, resClone));
          return res;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match(OFFLINE_URL)))
    );
  }
});
