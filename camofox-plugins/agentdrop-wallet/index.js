/**
 * Plugin camofox-browser: memuat extension wallet AgentDrop ke Camoufox.
 *
 * KENAPA PLUGIN INI TERLIHAT BERLEBITAN
 * ------------------------------------
 * Jalur yang wajar adalah meneruskan `addons` ke launchOptions(). Tapi
 * camofox-browser tidak melakukan itu — satu-satunya knob addon yang ia punya
 * adalah CAMOFOX_DISABLE_DEFAULT_ADDONS (server.js hanya mengirim
 * `exclude_addons`).
 *
 * Dan hook `browser:launching` TIDAK bisa dipakai secara naif, karena
 * camoufox-js sudah menyerialisasi seluruh config — termasuk `addons` — ke
 * env var CAMOU_CONFIG_N sebelum hook ini jalan:
 *
 *     // camoufox-js dist/utils.js
 *     const chunkSize = OS_NAME === "win" ? 2047 : 32767;
 *     const configStr = new TextDecoder().decode(updatedConfigData);
 *     for (let i = 0; i < configStr.length; i += chunkSize) {
 *       envVars[`CAMOU_CONFIG_${Math.floor(i / chunkSize) + 1}`] = configStr.slice(i, i + chunkSize);
 *     }
 *
 * Jadi yang dilakukan plugin ini adalah membedah chunk env itu, menambahkan
 * path extension kita, lalu menyusunnya kembali.
 *
 * INI BERGANTUNG PADA FORMAT INTERNAL. Kalau camoufox-js mengubah cara
 * chunking, plugin ini harus GAGAL KERAS, bukan diam-diam meluncurkan browser
 * tanpa wallet. Karena itu setiap langkah memverifikasi asumsinya dan
 * melempar kalau tidak cocok.
 *
 * Konfigurasi (camofox.config.json):
 *   {
 *     "plugins": {
 *       "agentdrop-wallet": {
 *         "enabled": true,
 *         "addonPath": "/app/extensions/agentdrop-wallet"
 *       }
 *     }
 *   }
 */

import fs from 'node:fs';
import path from 'node:path';

const ENV_PREFIX = 'CAMOU_CONFIG_';
const LINUX_CHUNK = 32767;   // dari camoufox-js dist/utils.js
const WIN_CHUNK = 2047;

function fail(msg) {
  // Sengaja melempar, bukan memperingatkan. Browser tanpa wallet terlihat
  // sama dengan browser dengan wallet sampai dApp pertama menolak — dan saat
  // itu agent sudah mengerjakan campaign sungguhan.
  throw new Error(`[agentdrop-wallet] ${msg}`);
}

function collectChunks(env) {
  const keys = Object.keys(env).filter((k) => k.startsWith(ENV_PREFIX));
  if (keys.length === 0) {
    fail('tidak menemukan env CAMOU_CONFIG_* — format internal camoufox-js '
      + 'mungkin berubah. Periksa dist/utils.js getEnvVars().');
  }

  const indexed = keys.map((k) => {
    const n = Number(k.slice(ENV_PREFIX.length));
    if (!Number.isInteger(n) || n < 1) {
      fail(`nama env ${k} tidak cocok dengan pola CAMOU_CONFIG_<angka>`);
    }
    return { n, key: k, value: env[k] };
  }).sort((a, b) => a.n - b.n);

  // Chunk harus berurutan tanpa lubang. Kalau ada yang hilang, JSON-nya
  // pasti rusak dan lebih baik berhenti di sini.
  for (let i = 0; i < indexed.length; i += 1) {
    if (indexed[i].n !== i + 1) {
      fail(`chunk env tidak berurutan: mengharapkan ${i + 1}, mendapat ${indexed[i].n}`);
    }
  }
  return indexed;
}

function detectChunkSize(indexed) {
  if (indexed.length >= 2) {
    // Chunk pertama selalu penuh, jadi panjangnya = ukuran chunk.
    return indexed[0].value.length;
  }
  // Hanya satu chunk: tidak bisa ditebak dari data. Container ini Linux.
  return LINUX_CHUNK;
}

function rechunk(str, size) {
  const out = {};
  for (let i = 0; i < str.length; i += size) {
    out[`${ENV_PREFIX}${Math.floor(i / size) + 1}`] = str.slice(i, i + size);
  }
  return out;
}

export function register(app, ctx) {
  const cfg = (ctx.config?.plugins?.['agentdrop-wallet']) || {};
  const addonPath = cfg.addonPath || '/app/extensions/agentdrop-wallet';

  // Verifikasi di awal, bukan saat browser diluncurkan. confirm_paths Camoufox
  // mensyaratkan DIREKTORI yang berisi manifest.json — bukan file .xpi.
  if (!fs.existsSync(addonPath) || !fs.statSync(addonPath).isDirectory()) {
    fail(`addonPath ${addonPath} bukan direktori. Camoufox menolak .xpi; `
      + 'yang dibutuhkan adalah addon yang sudah diekstrak.');
  }
  const manifest = path.join(addonPath, 'manifest.json');
  if (!fs.existsSync(manifest)) {
    fail(`${manifest} tidak ada. Camoufox confirm_paths() akan menolak path ini.`);
  }

  ctx.events.on('browser:launching', ({ options }) => {
    if (!options || !options.env) {
      fail('options.env tidak ada saat browser:launching');
    }

    const indexed = collectChunks(options.env);
    const json = indexed.map((c) => c.value).join('');

    let config;
    try {
      config = JSON.parse(json);
    } catch (err) {
      fail(`gagal mem-parse config dari ${indexed.length} chunk env: ${err.message}. `
        + 'Format internal camoufox-js kemungkinan berubah.');
    }

    const before = Array.isArray(config.addons) ? config.addons.slice() : [];
    if (before.includes(addonPath)) return;   // sudah ada, idempotent

    config.addons = [...before, addonPath];

    const size = detectChunkSize(indexed);
    const next = rechunk(JSON.stringify(config), size);

    // Hapus chunk lama dulu: kalau config baru lebih pendek, sisa chunk lama
    // akan terbaca sebagai bagian dari JSON dan merusaknya.
    for (const c of indexed) delete options.env[c.key];
    Object.assign(options.env, next);

    ctx.log?.('info', 'agentdrop-wallet: extension ditambahkan ke launch config', {
      addonPath,
      addonsBefore: before.length,
      addonsAfter: config.addons.length,
      chunks: Object.keys(next).length,
      chunkSize: size,
    });
  });

  ctx.log?.('info', 'agentdrop-wallet plugin aktif', { addonPath });
}

export default { register };
