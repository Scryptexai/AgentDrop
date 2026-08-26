/**
 * Test untuk index.js plugin agentdrop-wallet.
 *
 * Jalankan:  node camofox-plugins/agentdrop-wallet/plugin.test.mjs
 *
 * Yang diuji adalah bagian paling rapuh dari seluruh setup: plugin ini
 * membedah env CAMOU_CONFIG_N yang diserialisasi camoufox-js. Kalau logika
 * chunk-nya salah, extension tidak termuat DAN browser tetap jalan normal —
 * kegagalannya senyap sampai dApp pertama menolak.
 */
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ADDON = path.resolve(HERE, '../../extensions/agentdrop-wallet');

const mod = await import('./index.js');

// --- tiru persis getEnvVars() di camoufox-js dist/utils.js ------------------
function chunkLikeCamoufoxJs(config, chunkSize) {
  const str = JSON.stringify(config);
  const env = {};
  for (let i = 0; i < str.length; i += chunkSize) {
    env[`CAMOU_CONFIG_${Math.floor(i / chunkSize) + 1}`] = str.slice(i, i + chunkSize);
  }
  return env;
}

function makeCtx(addonPath = ADDON) {
  const events = new EventEmitter();
  const logs = [];
  return {
    ctx: {
      events,
      config: { plugins: { 'agentdrop-wallet': { enabled: true, addonPath } } },
      log: (level, msg, extra) => logs.push({ level, msg, extra }),
    },
    logs,
    fire: (options) => events.emit('browser:launching', { options }),
  };
}

let passed = 0;
function test(name, fn) {
  try { fn(); passed += 1; console.log(`  ok   ${name}`); }
  catch (err) { console.error(`  FAIL ${name}\n       ${err.message}`); process.exitCode = 1; }
}

test('addon ditambahkan dan config tetap JSON valid (1 chunk)', () => {
  const { ctx, fire } = makeCtx();
  mod.register(null, ctx);
  const env = chunkLikeCamoufoxJs({ navigator: { userAgent: 'x' }, addons: ['/ub'] }, 32767);
  const options = { env };
  fire(options);
  const keys = Object.keys(options.env).filter((k) => k.startsWith('CAMOU_CONFIG_'));
  const cfg = JSON.parse(keys.sort((a, b) => +a.split('_')[2] - +b.split('_')[2])
    .map((k) => options.env[k]).join(''));
  assert.deepEqual(cfg.addons, ['/ub', ADDON]);
  assert.equal(cfg.navigator.userAgent, 'x', 'field lain harus utuh');
});

test('config besar yang terpecah banyak chunk tetap utuh', () => {
  const { ctx, fire } = makeCtx();
  mod.register(null, ctx);
  // Buat config yang jauh melebihi satu chunk supaya terpecah.
  const big = { padding: 'A'.repeat(120000), addons: [] };
  const env = chunkLikeCamoufoxJs(big, 32767);
  const nBefore = Object.keys(env).length;
  assert.ok(nBefore >= 4, `harapan >=4 chunk, dapat ${nBefore}`);
  const options = { env };
  fire(options);
  const keys = Object.keys(options.env).filter((k) => k.startsWith('CAMOU_CONFIG_'));
  const cfg = JSON.parse(keys.sort((a, b) => +a.split('_')[2] - +b.split('_')[2])
    .map((k) => options.env[k]).join(''));
  assert.equal(cfg.padding.length, 120000, 'payload besar harus utuh');
  assert.deepEqual(cfg.addons, [ADDON]);
});

test('ukuran chunk mengikuti yang asli, bukan hardcode', () => {
  const { ctx, fire } = makeCtx();
  mod.register(null, ctx);
  // Pakai ukuran chunk Windows (2047) — plugin harus mengikutinya.
  const env = chunkLikeCamoufoxJs({ a: 'B'.repeat(5000), addons: [] }, 2047);
  const options = { env };
  fire(options);
  const keys = Object.keys(options.env).filter((k) => k.startsWith('CAMOU_CONFIG_'))
    .sort((a, b) => +a.split('_')[2] - +b.split('_')[2]);
  assert.equal(options.env[keys[0]].length, 2047, 'chunk pertama harus tetap 2047');
});

test('idempoten: memanggil dua kali tidak menduplikasi', () => {
  const { ctx, fire } = makeCtx();
  mod.register(null, ctx);
  const options = { env: chunkLikeCamoufoxJs({ addons: [] }, 32767) };
  fire(options);
  fire(options);
  const keys = Object.keys(options.env).filter((k) => k.startsWith('CAMOU_CONFIG_'));
  const cfg = JSON.parse(keys.sort((a, b) => +a.split('_')[2] - +b.split('_')[2])
    .map((k) => options.env[k]).join(''));
  assert.deepEqual(cfg.addons, [ADDON], 'harus tepat satu entri');
});

test('chunk yang hilang membuat plugin GAGAL, bukan lanjut diam-diam', () => {
  const { ctx, fire } = makeCtx();
  mod.register(null, ctx);
  const env = chunkLikeCamoufoxJs({ padding: 'A'.repeat(120000) }, 32767);
  delete env.CAMOU_CONFIG_2;   // lubang di tengah
  assert.throws(() => fire({ env }), /tidak berurutan/);
});

test('JSON rusak membuat plugin GAGAL', () => {
  const { ctx, fire } = makeCtx();
  mod.register(null, ctx);
  assert.throws(() => fire({ env: { CAMOU_CONFIG_1: '{bukan json' } }), /gagal mem-parse/);
});

test('tanpa CAMOU_CONFIG sama sekali membuat plugin GAGAL', () => {
  const { ctx, fire } = makeCtx();
  mod.register(null, ctx);
  assert.throws(() => fire({ env: { PATH: '/usr/bin' } }), /tidak menemukan env CAMOU_CONFIG/);
});

test('addonPath yang tidak ada ditolak saat register', () => {
  const { ctx } = makeCtx('/tmp/pasti-tidak-ada-xyz');
  assert.throws(() => mod.register(null, ctx), /bukan direktori/);
});

test('.xpi ditolak — Camoufox butuh direktori terekstrak', () => {
  // manifest.json di dalam direktori addon harus benar-benar ada.
  assert.ok(fs.existsSync(path.join(ADDON, 'manifest.json')),
    'extensions/agentdrop-wallet/manifest.json harus ada');
  const m = JSON.parse(fs.readFileSync(path.join(ADDON, 'manifest.json'), 'utf-8'));
  assert.equal(m.manifest_version, 2);
  assert.deepEqual(m.background.scripts, ['config.local.js', 'background.js'],
    'config.local.js harus dimuat sebelum background.js');
  assert.ok(m.web_accessible_resources.includes('inject.js'),
    'inject.js harus web-accessible agar bisa disuntik ke halaman');
});

console.log(`\n${passed} test lolos`);
