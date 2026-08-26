/*
 * inject.js — berjalan di MAIN WORLD halaman (bukan dunia terisolasi extension).
 *
 * Inilah yang membuat dApp melihat window.ethereum. Skrip ini TIDAK punya
 * akses ke token daemon; ia hanya meneruskan permintaan ke content.js lewat
 * window.postMessage, dan content.js yang bicara ke background.js.
 *
 * Kenapa tidak langsung fetch ke daemon dari sini?
 *   1. Token akan terlihat oleh halaman. Halaman bisa menandatangani apa pun.
 *   2. CORS akan memblokirnya.
 *   3. Policy engine tidak akan bisa melihat origin yang sebenarnya.
 */
(() => {
  'use strict';

  // Jangan menimpa wallet yang sudah ada (mis. halaman punya provider sendiri).
  if (window.ethereum && window.ethereum.isAgentDrop) return;

  const CHANNEL = 'agentdrop-wallet';
  const listeners = { connect: [], disconnect: [], chainChanged: [], accountsChanged: [], message: [] };
  const pending = new Map();
  let idSeq = 0;
  let connected = false;
  let chainId = null;
  let accounts = [];

  function nextId() {
    idSeq += 1;
    return `req-${idSeq}-${Date.now()}`;
  }

  // --- jalur balik dari content.js ----------------------------------------
  window.addEventListener('message', (ev) => {
    if (ev.source !== window) return;
    const d = ev.data;
    if (!d || d.__channel !== CHANNEL || d.__dir !== 'to-page') return;

    if (d.__kind === 'response') {
      const p = pending.get(d.id);
      if (!p) return;
      pending.delete(d.id);
      if (d.error) p.reject(makeError(d.error));
      else p.resolve(d.result);
      return;
    }

    if (d.__kind === 'event') {
      const cbs = listeners[d.event] || [];
      for (const cb of cbs) {
        try { cb(d.payload); } catch (e) { /* listener halaman tidak boleh mematikan kita */ }
      }
    }
  });

  function makeError(err) {
    // 4001 = user rejected (EIP-1193). 4900 = disconnected. 4901 = chain
    // tidak didukung. dApp memeriksa kode ini, jadi kodenya harus benar.
    const e = new Error(err.message || 'AgentDrop: permintaan ditolak');
    e.code = err.code || 4001;
    if (err.data) e.data = err.data;
    return e;
  }

  function call(method, params) {
    return new Promise((resolve, reject) => {
      const id = nextId();
      pending.set(id, { resolve, reject });
      window.postMessage({
        __channel: CHANNEL,
        __dir: 'to-ext',
        __kind: 'request',
        id,
        method,
        params: params || [],
      }, '*');
    });
  }

  const provider = {
    isAgentDrop: true,
    // Banyak dApp memeriksa isMetaMask. Kita TIDAK berbohong soal itu — kalau
    // kita mengaku MetaMask, dApp akan memanggil method khusus MetaMask yang
    // tidak kita punya dan gagal dengan cara yang membingungkan.
    isMetaMask: false,

    chainId: null,
    networkVersion: null,
    selectedAddress: null,

    async request({ method, params }) {
      if (typeof method !== 'string' || !method) {
        throw makeError({ message: 'method harus string', code: -32600 });
      }
      const out = await call(method, params);

      // Sinkronkan state lokal supaya properti lama tetap benar.
      if (method === 'eth_chainId' && typeof out === 'string') {
        if (chainId !== out) {
          chainId = out;
          provider.chainId = out;
          emit('chainChanged', out);
        }
        if (!connected) { connected = true; emit('connect', { chainId: out }); }
      }
      if ((method === 'eth_accounts' || method === 'eth_requestAccounts') && Array.isArray(out)) {
        accounts = out;
        provider.selectedAddress = out[0] || null;
        if (!connected) { connected = true; emit('connect', { chainId }); }
      }
      return out;
    },

    // API lama yang masih dipakai banyak dApp airdrop.
    async enable() {
      return this.request({ method: 'eth_requestAccounts' });
    },

    async send(methodOrPayload, paramsOrCb) {
      if (typeof methodOrPayload === 'string') {
        return this.request({ method: methodOrPayload, params: paramsOrCb || [] });
      }
      const cb = typeof paramsOrCb === 'function' ? paramsOrCb : null;
      try {
        const result = await this.request({
          method: methodOrPayload.method,
          params: methodOrPayload.params || [],
        });
        if (cb) cb(null, { id: methodOrPayload.id, jsonrpc: '2.0', result });
        return { id: methodOrPayload.id, jsonrpc: '2.0', result };
      } catch (err) {
        if (cb) cb(err, null);
        throw err;
      }
    },

    on(event, cb) {
      if (Array.isArray(listeners[event])) listeners[event].push(cb);
      return this;
    },

    removeListener(event, cb) {
      const arr = listeners[event];
      if (Array.isArray(arr)) {
        const i = arr.indexOf(cb);
        if (i >= 0) arr.splice(i, 1);
      }
      return this;
    },

    removeAllListeners(event) {
      if (event && Array.isArray(listeners[event])) listeners[event] = [];
      return this;
    },

    // Dipakai beberapa library untuk memeriksa kemampuan provider.
    isConnected() { return connected; },
  };

  function emit(event, payload) {
    for (const cb of (listeners[event] || [])) {
      try { cb(payload); } catch (e) { /* ignore */ }
    }
  }

  // Definisi non-writable supaya skrip halaman tidak bisa menimpanya dan
  // mengarahkan dApp ke wallet palsu.
  Object.defineProperty(window, 'ethereum', {
    value: provider,
    writable: false,
    configurable: false,
  });

  // EIP-6963: dApp modern menemukan provider lewat event ini, bukan dengan
  // membaca window.ethereum. Tanpa ini, dApp yang hanya pakai EIP-6963 tidak
  // akan pernah melihat kita.
  window.addEventListener('eip6963:requestProvider', () => {
    window.dispatchEvent(new CustomEvent('eip6963:announceProvider', {
      detail: Object.freeze({
        info: Object.freeze({
          uuid: 'a1d0e9f2-4b7c-4e21-9a35-agentdrop0001'.slice(0, 36),
          name: 'AgentDrop Wallet',
          icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg"/>',
          rdns: 'local.agentdrop.wallet',
        }),
        provider,
      }),
    }));
  });
})();
