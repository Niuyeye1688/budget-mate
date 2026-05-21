const CACHE_NAME = 'budget-mate-v2';
const urlsToCache = [
  '/',
  '/static/style.css',
  '/static/db.js',
  '/static/app-logic.js',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
      .catch(err => console.error('Cache install failed:', err))
  );
  self.skipWaiting();
});

self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;

  // 导航请求（HTML 页面）：优先返回缓存的 /，实现 SPA 离线访问
  if (request.mode === 'navigate') {
    event.respondWith(
      caches.match('/')
        .then(response => response || fetch(request))
    );
    return;
  }

  // 静态资源：缓存优先，网络失败回退缓存
  event.respondWith(
    caches.match(request).then(cached => {
      if (cached) return cached;
      return fetch(request).catch(() => {
        // 图片请求失败时返回空响应，避免页面崩溃
        if (request.destination === 'image') {
          return new Response('', { status: 204, statusText: 'No Content' });
        }
      });
    })
  );
});
