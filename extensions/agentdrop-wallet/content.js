/*
 * content.js — jembatan antara dunia halaman dan background extension.
 *
 * Berjalan di dunia TERISOLASI (punya akses browser.runtime, tidak punya akses
 * window.ethereum halaman). Tugasnya cuma dua: menyuntik inject.js ke dunia
 * halaman, dan meneruskan pesan dua arah.
 *
 * Tidak ada logika keputusan di sini. Tidak ada token di sini.
 */
(() => {
  'use strict';

  const CHANNEL = 'agentdrop-wallet';

  // --- 1. Suntik inject.js ke main world ----------------------------------
  // Harus sedini mungkin. content script ini sudah run_at: document_start.
  try {
    const s = document.createElement('script');
    s.src = browser.runtime.getURL('inject.js');
    s.async = false;   // async=true bisa membuatnya jalan setelah skrip dApp
    (document.head || document.documentElement).appendChild(s);
    s.onload = () => s.remove();
  } catch (err) {
    // CSP halaman bisa menolak penyuntikan. Kalau ini terjadi dApp tidak akan
    // melihat wallet sama sekali — lebih baik terdengar keras daripada senyap.
    console.warn('[AgentDrop] gagal menyuntik provider:', err && err.message);
  }

  // --- 2. Halaman -> extension --------------------------------------------
  window.addEventListener('message', (ev) => {
    if (ev.source !== window) return;
    const d = ev.data;
    if (!d || d.__channel !== CHANNEL || d.__dir !== 'to-ext') return;

    // origin dikirim ke daemon supaya policy engine bisa melihat situs mana
    // yang meminta. location.origin diambil di sini, BUKAN dipercaya dari
    // halaman — halaman bisa memalsukan field apa pun di postMessage.
    browser.runtime
      .sendMessage({
        type: 'agentdrop-sign',
        id: d.id,
        method: d.method,
        params: d.params,
        origin: location.origin,
        href: location.href,
      })
      .then((resp) => {
        window.postMessage({
          __channel: CHANNEL,
          __dir: 'to-page',
          __kind: 'response',
          id: d.id,
          result: resp && resp.result,
          error: resp && resp.error,
        }, '*');
      })
      .catch((err) => {
        window.postMessage({
          __channel: CHANNEL,
          __dir: 'to-page',
          __kind: 'response',
          id: d.id,
          error: { message: (err && err.message) || 'daemon tidak menjawab', code: 4900 },
        }, '*');
      });
  });

  // --- 3. Event dari background -> halaman --------------------------------
  browser.runtime.onMessage.addListener((msg) => {
    if (!msg || msg.type !== 'agentdrop-event') return;
    window.postMessage({
      __channel: CHANNEL,
      __dir: 'to-page',
      __kind: 'event',
      event: msg.event,
      payload: msg.payload,
    }, '*');
  });
})();
