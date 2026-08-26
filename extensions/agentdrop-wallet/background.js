/*
 * background.js — satu-satunya bagian yang memegang token daemon.
 *
 * Token TIDAK pernah dikirim ke content script atau ke halaman. Halaman hanya
 * pernah melihat hasil, tidak pernah kredensial.
 *
 * Konfigurasi (URL daemon + token) dibaca dari config.local.js, yang dibuat
 * oleh scripts/setup.sh dari .env. File itu sengaja terpisah supaya:
 *   - extension ini bisa di-commit tanpa membawa secret
 *   - token bisa dirotasi tanpa menyunting kode extension
 */
(() => {
  'use strict';

  const cfg = (typeof AGENTDROP_CONFIG !== 'undefined' && AGENTDROP_CONFIG) || {};
  const BASE = cfg.baseUrl || 'http://127.0.0.1:9721';
  const TOKEN = cfg.token || '';
  const TIMEOUT_MS = cfg.timeoutMs || 60000;

  let warnedNoToken = false;

  async function askDaemon(method, params, origin) {
    if (!TOKEN) {
      if (!warnedNoToken) {
        warnedNoToken = true;
        console.error('[AgentDrop] AGENTDROP_SIGNER_TOKEN kosong. Semua permintaan '
          + 'signing akan ditolak. Jalankan ulang scripts/setup.sh setelah mengisi .env.');
      }
      throw new Error('token daemon belum dikonfigurasi');
    }

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    try {
      const res = await fetch(BASE + '/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-AgentDrop-Token': TOKEN,
        },
        body: JSON.stringify({ method, params, origin }),
        signal: ctrl.signal,
      });

      let body;
      try { body = await res.json(); }
      catch (e) { throw new Error(`daemon menjawab bukan JSON (HTTP ${res.status})`); }

      if (res.status === 403) throw new Error('daemon menolak token');
      if (res.status >= 500) throw new Error(body.error || `daemon error HTTP ${res.status}`);

      // Daemon menandai penolakan kebijakan dengan rejected:true. Itu BUKAN
      // kesalahan teknis — itu keputusan. Kita teruskan sebagai 4001 supaya
      // dApp menampilkannya seperti penolakan wallet biasa.
      if (body.rejected) {
        const err = new Error(body.error || 'ditolak oleh kebijakan');
        err.code = 4001;
        throw err;
      }
      if (body.error) throw new Error(body.error);
      return body.result;
    } catch (err) {
      if (err && err.name === 'AbortError') {
        throw new Error(`daemon tidak menjawab dalam ${TIMEOUT_MS}ms`);
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  browser.runtime.onMessage.addListener((msg, sender) => {
    if (!msg || msg.type !== 'agentdrop-sign') return undefined;

    // sender.origin adalah apa yang dilihat browser, bukan apa yang diklaim
    // halaman. Kalau keduanya ada dan berbeda, yang dipakai adalah milik
    // browser — content script mengirim location.origin yang sudah tepercaya,
    // tapi kita tetap lebih percaya sender.
    const origin = (sender && sender.origin) || msg.origin || '';

    return askDaemon(msg.method, msg.params, origin)
      .then((result) => ({ result }))
      .catch((err) => ({
        error: { message: (err && err.message) || 'gagal', code: (err && err.code) || 4001 },
      }));
  });

  // Kesehatan daemon, supaya kegagalan terlihat di console browser alih-alih
  // muncul nanti sebagai "wallet tidak merespons".
  async function checkDaemon() {
    try {
      const res = await fetch(BASE + '/health', { method: 'GET' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch (err) {
      console.warn('[AgentDrop] daemon signing tidak terjangkau di', BASE,
        '—', err && err.message,
        '— jalankan tools/signing_daemon.py');
    }
  }
  checkDaemon();
})();
