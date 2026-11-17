/* Racine du site GARÉo : plus de service worker ici (l'appli de relevé est passée dans releve-acc/).
   Ce fichier remplace l'ancien : il vide les anciens caches « gareo-photo- » puis se désinscrit. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k.startsWith('gareo-photo-')) await caches.delete(k);
  await self.registration.unregister();
  for (const c of await self.clients.matchAll({type:'window'})) c.navigate(c.url);
})()));
