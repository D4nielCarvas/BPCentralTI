self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open('bpti-v1').then((cache) => {
      return cache.addAll([
        '/static/icon.svg'
      ]);
    })
  );
});

self.addEventListener('fetch', (e) => {
  e.respondWith(
    caches.match(e.request).then((response) => {
      return response || fetch(e.request);
    })
  );
});
