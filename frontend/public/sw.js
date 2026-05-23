// Service Worker di pocket-dnd.
//
// Strategia (deliberatamente minimale):
//   - shell della SPA cacheata, cosi' l'app si apre anche se la connessione
//     al backend salta — al pub capita di continuo (CLAUDE.md).
//   - i dati (API/WS) NON vengono mai cacheati: lo stato vero e' sul server
//     ed e' autoritativo (DECISIONS.md D5). Cachearli darebbe stato stale.
//   - bypass totale per metodi non-GET e per /api/* e /ws/*.

const CACHE = 'pocket-dnd-v1'
const SHELL = ['/', '/master', '/manifest.webmanifest', '/icon.svg']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL))
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys()
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    await self.clients.claim()
  })())
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws/')) return

  // asset di build (hash nei nomi): cache-first, popolato on demand.
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(
      caches.match(req).then((cached) =>
        cached ||
        fetch(req).then((resp) => {
          const copy = resp.clone()
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {})
          return resp
        })
      )
    )
    return
  }

  // pagine della SPA: network-first con fallback alla cache (e poi a '/'
  // come ultima spiaggia, cosi' l'app si apre sempre).
  event.respondWith(
    fetch(req).then((resp) => {
      const copy = resp.clone()
      caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {})
      return resp
    }).catch(() =>
      caches.match(req).then((cached) => cached || caches.match('/'))
    )
  )
})
