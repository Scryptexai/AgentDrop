#!/usr/bin/env node
"use strict";
/**
 * AgentDrop computer-use MCP server (CDP-based, zero dependencies).
 *
 * Why CDP and not a desktop-automation server: AgentDrop's agents drive
 * a headless/headed CHROME profile (persistent profile + CDP port from
 * data/profile_registry.json). OS-level mouse/keyboard (desktop
 * computer-use) cannot reach a headless browser. This server exposes the
 * same 24-tool computer-use vocabulary the Python engine uses, so a
 * Hermes session and the worker engine behave identically.
 *
 * Protocol: MCP over stdio (newline-delimited JSON-RPC 2.0).
 * Requires Node >= 21 (global fetch + WebSocket).
 *
 * Env:
 *   CDP_HOST   (default 127.0.0.1)
 *   CDP_PORT   (default 9223 — the "execution" profile)
 *   CDP_SETTLE_MS  (default 600 — render settle delay before screenshots)
 */

const zlib = require("zlib");

const CDP_HOST = process.env.CDP_HOST || "127.0.0.1";
const CDP_PORT = process.env.CDP_PORT || "9223";
const SETTLE_MS = Number(process.env.CDP_SETTLE_MS || 600);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------------------
// Minimal PNG decoder (8-bit, color type 2=RGB / 6=RGBA) — just enough to
// diff screenshots for computer_verify_change. Zero dependencies.
// ---------------------------------------------------------------------------
function decodePng(buf) {
  if (buf.readUInt32BE(0) !== 0x89504e47) throw new Error("not a PNG");
  let off = 8;
  let width = 0, height = 0, bitDepth = 0, colorType = 0;
  const idat = [];
  while (off < buf.length) {
    const len = buf.readUInt32BE(off);
    const type = buf.toString("ascii", off + 4, off + 8);
    const data = buf.subarray(off + 8, off + 8 + len);
    if (type === "IHDR") {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data.readUInt8(8);
      colorType = data.readUInt8(9);
    } else if (type === "IDAT") {
      idat.push(data);
    } else if (type === "IEND") {
      break;
    }
    off += 12 + len;
  }
  if (bitDepth !== 8 || (colorType !== 2 && colorType !== 6)) {
    throw new Error(`unsupported PNG (bitDepth=${bitDepth} colorType=${colorType})`);
  }
  const channels = colorType === 6 ? 4 : 3;
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const stride = width * channels;
  const px = Buffer.alloc(height * stride);
  let prev = Buffer.alloc(stride);
  let pos = 0;
  for (let y = 0; y < height; y++) {
    const filter = raw[pos++];
    const line = Buffer.from(raw.subarray(pos, pos + stride));
    pos += stride;
    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? line[x - channels] : 0;
      const b = prev[x];
      const c = x >= channels ? prev[x - channels] : 0;
      let v = line[x];
      if (filter === 1) v = (v + a) & 0xff;
      else if (filter === 2) v = (v + b) & 0xff;
      else if (filter === 3) v = (v + ((a + b) >> 1)) & 0xff;
      else if (filter === 4) {
        const p = a + b - c;
        const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
        const pr = pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
        v = (v + pr) & 0xff;
      }
      px[y * stride + x] = v;
    }
    prev = line;
  }
  return { width, height, channels, px };
}

function grayscale(img) {
  const n = img.width * img.height;
  const g = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const o = i * img.channels;
    g[i] = 0.299 * img.px[o] + 0.587 * img.px[o + 1] + 0.114 * img.px[o + 2];
  }
  return g;
}

function diffStats(a, b) {
  const A = grayscale(a), B = grayscale(b);
  const n = Math.min(A.length, B.length);
  let sum = 0, big = 0;
  for (let i = 0; i < n; i++) {
    const d = Math.abs(A[i] - B[i]);
    sum += d;
    if (d > 30) big++;
  }
  return { mean: sum / n, localFraction: big / n };
}

// ---------------------------------------------------------------------------
// CDP client (one target at a time; lazily connects)
// ---------------------------------------------------------------------------
let cdp = null;

async function getCDP(targetId) {
  const base = `http://${CDP_HOST}:${CDP_PORT}`;
  const targets = await (await fetch(`${base}/json/list`)).json();
  let page;
  if (targetId) {
    page = targets.find((t) => t.id === targetId && t.type === "page");
  } else {
    page = targets.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
  }
  if (!page || !page.webSocketDebuggerUrl) {
    throw new Error(`no page target on ${base} (is the profile browser running? scripts/start-browser.sh)`);
  }
  const c = { ws: null, target: page, id: 0, pending: new Map(), listeners: new Map() };
  c.ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => {
    c.ws.onopen = res;
    c.ws.onerror = () => rej(new Error("CDP websocket connect failed"));
  });
  c.ws.onmessage = (ev) => {
    let m;
    try { m = JSON.parse(ev.data); } catch { return; }
    if (m.id != null && c.pending.has(m.id)) {
      const { res, rej } = c.pending.get(m.id);
      c.pending.delete(m.id);
      if (m.error) rej(new Error(m.error.message));
      else res(m.result || {});
    } else if (m.method) {
      (c.listeners.get(m.method) || []).forEach((cb) => {
        try { cb(m.params || {}); } catch { /* ignore */ }
      });
    }
  };
  c.call = async (method, params = {}, timeout = 30000) => {
    const id = ++c.id;
    const p = new Promise((res, rej) => {
      c.pending.set(id, { res, rej });
      setTimeout(() => {
        if (c.pending.has(id)) { c.pending.delete(id); rej(new Error(`CDP timeout: ${method}`)); }
      }, timeout);
    });
    c.ws.send(JSON.stringify({ id, method, params }));
    return p;
  };
  cdp = c;
  await c.call("Page.enable").catch(() => {});
  await c.call("Runtime.enable").catch(() => {});
  return c;
}

async function cdpCall(method, params = {}) {
  const c = await getCDP();
  return c.call(method, params);
}

async function cdpListTargets() {
  const base = `http://${CDP_HOST}:${CDP_PORT}`;
  return (await (await fetch(`${base}/json/list`)).json())
    .filter((t) => t.type === "page")
    .map((t) => ({ targetId: t.id, url: t.url, title: t.title, ws: !!t.webSocketDebuggerUrl }));
}

async function cdpReconnectTo(targetId) {
  if (cdp) { try { cdp.ws.close(); } catch { /* ignore */ } cdp = null; }
  await getCDP(targetId);
}

// ---------------------------------------------------------------------------
// Input primitives (human-like: move before click, stepped drags, real keys)
// ---------------------------------------------------------------------------
const SPECIAL_KEYS = {
  Enter: ["Enter", 13], Tab: ["Tab", 9], Backspace: ["Backspace", 8],
  Delete: ["Delete", 46], Space: ["Space", 32], Escape: ["Escape", 27],
  ArrowLeft: ["ArrowLeft", 37], ArrowUp: ["ArrowUp", 38],
  ArrowRight: ["ArrowRight", 39], ArrowDown: ["ArrowDown", 40],
  Home: ["Home", 36], End: ["End", 35], PageUp: ["PageUp", 33],
  PageDown: ["PageDown", 34], F5: ["F5", 116],
};
const PUNCT = { ".": "Period", ",": "Comma", "?": "Question", "!": "Exclamation",
  "/": "Slash", ":": "Colon", ";": "Semicolon", "'": "Quote", '"': "Quote",
  "(": "BracketLeft", ")": "BracketRight", "[": "BracketLeft", "]": "BracketRight",
  "-": "Minus", "_": "Minus", "=": "Equal", "+": "Equal", "@": "Digit2" };
const MODIFIERS = {
  ctrl: ["ControlLeft", "Control", 17], shift: ["ShiftLeft", "Shift", 16],
  alt: ["AltLeft", "Alt", 18], meta: ["MetaLeft", "Meta", 91], cmd: ["MetaLeft", "Meta", 91],
};

function charKey(ch) {
  if (/[a-zA-Z]/.test(ch)) return [`Key${ch.toUpperCase()}`, ch.toUpperCase().charCodeAt(0)];
  if (/[0-9]/.test(ch)) return [`Digit${ch}`, ch.charCodeAt(0)];
  return [PUNCT[ch] || "", ch.charCodeAt(0)];
}

async function mouse(type, x, y, extra = {}) {
  await cdpCall("Input.dispatchMouseEvent", {
    type, x: Math.round(x), y: Math.round(y),
    button: extra.button || "none", clickCount: extra.clickCount || 1,
    ...Object.fromEntries(Object.entries(extra).filter(([k]) => !["button", "clickCount"].includes(k))),
  });
}

async function dispatchKey(type, key, text) {
  let code, vk, k = key;
  if (SPECIAL_KEYS[key]) [code, vk] = SPECIAL_KEYS[key];
  else if (key.length === 1) [code, vk] = charKey(key);
  else throw new Error(`unsupported key: ${key}`);
  const params = { type, key: k, code, windowsVirtualKeyCode: vk };
  await cdpCall("Input.dispatchKeyEvent", params);
  if (text) await cdpCall("Input.dispatchKeyEvent", { type: "char", text, unmodifiedText: text });
}

let lastShot = null;   // {b64, bytes}
let prevShot = null;   // previous screenshot (for verify_change)

async function takeScreenshot() {
  const r = await cdpCall("Page.captureScreenshot", { format: "png", fromSurface: true });
  prevShot = lastShot;
  lastShot = { b64: r.data, bytes: Buffer.from(r.data, "base64") };
  return lastShot;
}

// ---------------------------------------------------------------------------
// Tool definitions (24)
// ---------------------------------------------------------------------------
const tools = [
  {
    name: "computer_screenshot",
    description: "Capture the current browser viewport as a PNG (base64). This is what the vision model sees.",
    inputSchema: { type: "object", properties: {} },
    handler: async () => {
      await sleep(SETTLE_MS);
      const s = await takeScreenshot();
      return { image: s.b64, text: "screenshot captured" };
    },
  },
  {
    name: "computer_click",
    description: "Click at absolute pixel coordinates (mouse moves there first, like a human).",
    inputSchema: {
      type: "object",
      properties: {
        x: { type: "number" }, y: { type: "number" },
        button: { type: "string", enum: ["left", "right", "middle"] },
        clickCount: { type: "integer", minimum: 1, maximum: 3 },
      },
      required: ["x", "y"],
    },
    handler: async ({ x, y, button = "left", clickCount = 1 }) => {
      await mouse("mouseMoved", x, y);
      for (let i = 1; i <= clickCount; i++) {
        if (i > 1) await sleep(80);
        await mouse("mousePressed", x, y, { button, clickCount: i });
        await sleep(40);
        await mouse("mouseReleased", x, y, { button, clickCount: i });
      }
      await sleep(SETTLE_MS);
      return `clicked ${button} x${clickCount} at ${x},${y}`;
    },
  },
  {
    name: "computer_double_click",
    description: "Double-click at absolute pixel coordinates.",
    inputSchema: { type: "object", properties: { x: { type: "number" }, y: { type: "number" } }, required: ["x", "y"] },
    handler: async ({ x, y }) => { await tools.find((t) => t.name === "computer_click").handler({ x, y, clickCount: 2 }); return `double-clicked at ${x},${y}`; },
  },
  {
    name: "computer_right_click",
    description: "Right-click (context menu) at absolute pixel coordinates.",
    inputSchema: { type: "object", properties: { x: { type: "number" }, y: { type: "number" } }, required: ["x", "y"] },
    handler: async ({ x, y }) => { await tools.find((t) => t.name === "computer_click").handler({ x, y, button: "right" }); return `right-clicked at ${x},${y}`; },
  },
  {
    name: "computer_move",
    description: "Move the mouse to absolute pixel coordinates without clicking.",
    inputSchema: { type: "object", properties: { x: { type: "number" }, y: { type: "number" } }, required: ["x", "y"] },
    handler: async ({ x, y }) => { await mouse("mouseMoved", x, y); return `moved to ${x},${y}`; },
  },
  {
    name: "computer_drag",
    description: "Drag from (x,y) to (x2,y2) with interpolated mouse movement.",
    inputSchema: {
      type: "object",
      properties: { x: { type: "number" }, y: { type: "number" }, x2: { type: "number" }, y2: { type: "number" }, steps: { type: "integer" } },
      required: ["x", "y", "x2", "y2"],
    },
    handler: async ({ x, y, x2, y2, steps = 8 }) => {
      await mouse("mouseMoved", x, y);
      await mouse("mousePressed", x, y, { button: "left" });
      for (let i = 1; i <= steps; i++) {
        const t = i / steps;
        await mouse("mouseMoved", x + (x2 - x) * t, y + (y2 - y) * t);
        await sleep(16);
      }
      await mouse("mouseReleased", x2, y2, { button: "left" });
      await sleep(SETTLE_MS);
      return `dragged ${x},${y} -> ${x2},${y2}`;
    },
  },
  {
    name: "computer_scroll",
    description: "Wheel-scroll at pixel coordinates. direction up|down; amount = wheel steps (1 step ~120px).",
    inputSchema: {
      type: "object",
      properties: {
        x: { type: "number" }, y: { type: "number" },
        direction: { type: "string", enum: ["up", "down"] },
        amount: { type: "integer", minimum: 1, maximum: 20 },
      },
      required: ["direction"],
    },
    handler: async ({ x, y, direction, amount = 1 }) => {
      const c = await getCDP();
      let m;
      try { m = (await c.call("Page.getLayoutMetrics")).cssLayoutViewport; } catch { m = { width: 1280, height: 800 }; }
      const cx = x ?? m.width / 2, cy = y ?? m.height / 2;
      const per = 120;
      const sign = direction === "up" ? -1 : 1;
      for (let i = 0; i < amount; i++) {
        await mouse("mouseWheel", cx, cy, { deltaX: 0, deltaY: sign * per });
        await sleep(30);
      }
      await sleep(SETTLE_MS);
      return `scrolled ${direction} x${amount} at ${Math.round(cx)},${Math.round(cy)}`;
    },
  },
  {
    name: "computer_type",
    description: "Click (x,y) to focus a field, then type text with real key events.",
    inputSchema: {
      type: "object",
      properties: { x: { type: "number" }, y: { type: "number" }, text: { type: "string" } },
      required: ["x", "y", "text"],
    },
    handler: async ({ x, y, text }) => {
      await mouse("mouseMoved", x, y);
      await mouse("mousePressed", x, y, { button: "left" });
      await sleep(40);
      await mouse("mouseReleased", x, y, { button: "left" });
      for (const ch of text) {
        if (ch === "\n") await dispatchKey("rawKeyDown", "Enter");
        else if (ch === "\t") await dispatchKey("rawKeyDown", "Tab");
        else {
          await dispatchKey("rawKeyDown", ch);
          await dispatchKey("keyUp", ch, ch);
        }
      }
      await sleep(SETTLE_MS);
      return `typed ${JSON.stringify(text)} at ${x},${y}`;
    },
  },
  {
    name: "computer_key",
    description: "Press a single key (Enter, Tab, Backspace, ArrowDown, letters...).",
    inputSchema: { type: "object", properties: { key: { type: "string" } }, required: ["key"] },
    handler: async ({ key }) => {
      await dispatchKey("rawKeyDown", key);
      if (key.length === 1) await dispatchKey("keyUp", key, key);
      else await dispatchKey("keyUp", key);
      return `pressed ${key}`;
    },
  },
  {
    name: "computer_hotkey",
    description: "Press a key combination, e.g. keys=[\"ctrl\",\"c\"].",
    inputSchema: {
      type: "object",
      properties: { keys: { type: "array", items: { type: "string" }, minItems: 2 } },
      required: ["keys"],
    },
    handler: async ({ keys }) => {
      const [main, ...mods] = keys.length > 1 && MODIFIERS[keys[0]] ? [keys[1], ...keys.slice(2), keys[0]] : [keys[keys.length - 1], ...keys.slice(0, -1)];
      for (const m of mods) {
        if (!MODIFIERS[m]) throw new Error(`unknown modifier: ${m}`);
        const [code, k, vk] = MODIFIERS[m];
        await cdpCall("Input.dispatchKeyEvent", { type: "rawKeyDown", key: k, code, windowsVirtualKeyCode: vk });
      }
      if (main.length === 1 && !SPECIAL_KEYS[main]) {
        await dispatchKey("rawKeyDown", main);
        await cdpCall("Input.dispatchKeyEvent", { type: "char", text: main, unmodifiedText: main });
        await dispatchKey("keyUp", main);
      } else {
        await dispatchKey("rawKeyDown", main);
        await dispatchKey("keyUp", main);
      }
      for (const m of [...mods].reverse()) {
        const [code, k, vk] = MODIFIERS[m];
        await cdpCall("Input.dispatchKeyEvent", { type: "keyUp", key: k, code, windowsVirtualKeyCode: vk });
      }
      return `hotkey ${keys.join("+")}`;
    },
  },
  {
    name: "computer_wait",
    description: "Wait N seconds (for spinners / transitions to settle).",
    inputSchema: { type: "object", properties: { seconds: { type: "number", minimum: 0, maximum: 30 } }, required: ["seconds"] },
    handler: async ({ seconds }) => { await sleep(Math.min(30, seconds) * 1000); return `waited ${seconds}s`; },
  },
  {
    name: "computer_navigate",
    description: "Navigate the current tab to a URL and wait for load + settle.",
    inputSchema: { type: "object", properties: { url: { type: "string" } }, required: ["url"] },
    handler: async ({ url }) => {
      const c = await getCDP();
      const loaded = new Promise((res) => {
        const cb = () => res(true);
        c.listeners.set("Page.loadEventFired", [cb]);
        setTimeout(res, 15000);
      });
      await c.call("Page.navigate", { url });
      await loaded;
      await sleep(SETTLE_MS);
      return `navigated to ${url}`;
    },
  },
  {
    name: "computer_go_back",
    description: "Go back in history (Alt+ArrowLeft, like a human).",
    inputSchema: { type: "object", properties: {} },
    handler: async () => { await tools.find((t) => t.name === "computer_hotkey").handler({ keys: ["alt", "ArrowLeft"] }); await sleep(SETTLE_MS); return "went back"; },
  },
  {
    name: "computer_go_forward",
    description: "Go forward in history (Alt+ArrowRight).",
    inputSchema: { type: "object", properties: {} },
    handler: async () => { await tools.find((t) => t.name === "computer_hotkey").handler({ keys: ["alt", "ArrowRight"] }); await sleep(SETTLE_MS); return "went forward"; },
  },
  {
    name: "computer_reload",
    description: "Reload the page and wait for load + settle.",
    inputSchema: { type: "object", properties: {} },
    handler: async () => {
      const c = await getCDP();
      const loaded = new Promise((res) => {
        c.listeners.set("Page.loadEventFired", [() => res(true)]);
        setTimeout(res, 15000);
      });
      await c.call("Page.reload");
      await loaded;
      await sleep(SETTLE_MS);
      return "reloaded";
    },
  },
  {
    name: "computer_get_url",
    description: "Current tab URL (metadata only — never an interaction target).",
    inputSchema: { type: "object", properties: {} },
    handler: async () => {
      const r = await cdpCall("Runtime.evaluate", { expression: "location.href", returnByValue: true });
      return r.result && r.result.value ? r.result.value : "";
    },
  },
  {
    name: "computer_get_title",
    description: "Current tab title (metadata only).",
    inputSchema: { type: "object", properties: {} },
    handler: async () => {
      const r = await cdpCall("Runtime.evaluate", { expression: "document.title", returnByValue: true });
      return r.result && r.result.value ? r.result.value : "";
    },
  },
  {
    name: "computer_screen_size",
    description: "Current viewport size in pixels (for grounding coordinates).",
    inputSchema: { type: "object", properties: {} },
    handler: async () => {
      const m = (await (await getCDP()).call("Page.getLayoutMetrics")).cssLayoutViewport;
      return { width: Math.round(m.width), height: Math.round(m.height) };
    },
  },
  {
    name: "computer_list_tabs",
    description: "List open page targets: targetId, url, title.",
    inputSchema: { type: "object", properties: {} },
    handler: async () => cdpListTargets(),
  },
  {
    name: "computer_new_tab",
    description: "Open a new tab (optionally at a URL) and switch to it.",
    inputSchema: { type: "object", properties: { url: { type: "string" } } },
    handler: async ({ url = "about:blank" }) => {
      const r = await cdpCall("Target.createTarget", { url });
      await cdpReconnectTo(r.targetId);
      return { targetId: r.targetId, url };
    },
  },
  {
    name: "computer_close_tab",
    description: "Close a tab (default: the current one's target).",
    inputSchema: { type: "object", properties: { targetId: { type: "string" } } },
    handler: async ({ targetId }) => {
      const c = await getCDP();
      const id = targetId || c.target.id;
      await c.call("Target.closeTarget", { targetId: id });
      cdp = null;
      return { closed: id };
    },
  },
  {
    name: "computer_switch_tab",
    description: "Attach to a different tab by targetId.",
    inputSchema: { type: "object", properties: { targetId: { type: "string" } }, required: ["targetId"] },
    handler: async ({ targetId }) => { await cdpReconnectTo(targetId); return { attached: targetId }; },
  },
  {
    name: "computer_verify_change",
    description: "Pixel-diff the last two screenshots (e.g. after an action). Returns changed + stats. The loop's honesty check.",
    inputSchema: {
      type: "object",
      properties: { meanThreshold: { type: "number" }, localFraction: { type: "number" } },
    },
    handler: async ({ meanThreshold = 0.3, localFraction = 0.0005 } = {}) => {
      if (!lastShot || !prevShot) return { changed: null, note: "take two screenshots first (computer_screenshot)" };
      const A = decodePng(prevShot.bytes);
      const B = decodePng(lastShot.bytes);
      const s = diffStats(A, B);
      return {
        changed: s.mean > meanThreshold || s.localFraction > localFraction,
        meanDiff: Number(s.mean.toFixed(4)),
        localChangeFraction: Number(s.localFraction.toFixed(6)),
      };
    },
  },
  {
    name: "computer_detect_auth",
    description: "Screenshot + pixel heuristics hinting at a CAPTCHA / auth-wall / wallet modal. The VISION MODEL makes the final call — this only localizes suspicious UI.",
    inputSchema: { type: "object", properties: {} },
    handler: async () => {
      await sleep(SETTLE_MS);
      const s = await takeScreenshot();
      const img = decodePng(s.bytes);
      const { width, height, px, channels } = img;
      const edge = (x0, y0, x1, y1) => {
        let e = 0, n = 0;
        for (let y = y0; y < y1; y += 2) {
          for (let x = x0; x < x1 - 2; x += 2) {
            const i = (y * width + x) * channels;
            const l = 0.299 * px[i] + 0.587 * px[i + 1] + 0.114 * px[i + 2];
            const j = (y * width + x + 2) * channels;
            const r = 0.299 * px[j] + 0.587 * px[j + 1] + 0.114 * px[j + 2];
            const k = ((y + 2) * width + x) * channels;
            const dn = 0.299 * px[k] + 0.587 * px[k + 1] + 0.114 * px[k + 2];
            e += Math.abs(l - r) + Math.abs(l - dn);
            n += 2;
          }
        }
        return e / Math.max(1, n);
      };
      const cw = Math.floor(width * 0.5), ch = Math.floor(height * 0.5);
      const cx0 = Math.floor((width - cw) / 2), cy0 = Math.floor((height - ch) / 2);
      const centerEdge = edge(cx0, cy0, cx0 + cw, cy0 + ch);
      const perimEdge = (edge(0, 0, width, Math.floor(height * 0.2)) + edge(0, Math.floor(height * 0.8), width, height)) / 2;
      return {
        image: s.b64,
        centerEdgeDensity: Number(centerEdge.toFixed(2)),
        peripheryEdgeDensity: Number(perimEdge.toFixed(2)),
        modalLikely: centerEdge > 4 * Math.max(0.5, perimEdge) && centerEdge > 8,
        note: "pixel hint only — confirm with the vision model (captcha_detected / wallet_prompt_detected)",
      };
    },
  },
];

// ---------------------------------------------------------------------------
// MCP over stdio
// ---------------------------------------------------------------------------
function asContent(result) {
  if (result && typeof result === "object" && result.image) {
    const out = [{ type: "image", data: result.image, mimeType: "image/png" }];
    const rest = { ...result };
    delete rest.image;
    out.push({ type: "text", text: JSON.stringify(rest, null, 2) });
    return out;
  }
  const text = typeof result === "string" ? result : JSON.stringify(result, null, 2);
  return [{ type: "text", text }];
}

function handleMessage(msg) {
  try {
    if (msg.method === "initialize") {
      return respond(msg.id, {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: "agentdrop-computer-use", version: "0.1.0" },
      });
    }
    if (msg.method === "notifications/initialized") return;
    if (msg.method === "ping") return respond(msg.id, {});
    if (msg.method === "tools/list") return respond(msg.id, { tools });
    if (msg.method === "tools/call") {
      const name = msg.params && msg.params.name;
      const args = (msg.params && msg.params.arguments) || {};
      const t = tools.find((x) => x.name === name);
      if (!t) return fail(msg.id, -32601, `unknown tool: ${name}`);
      t.handler(args)
        .then((result) => respond(msg.id, { content: asContent(result) }))
        .catch((e) => respond(msg.id, { content: [{ type: "text", text: `error: ${e.message}` }], isError: true }));
      return;
    }
    if (msg.id != null) fail(msg.id, -32601, `unknown method: ${msg.method}`);
  } catch (e) {
    if (msg.id != null) fail(msg.id, -32603, e.message);
  }
}

function respond(id, result) { process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id, result }) + "\n"); }
function fail(id, code, message) { process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id, error: { code, message } }) + "\n"); }

let buffer = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  buffer += chunk;
  let i;
  while ((i = buffer.indexOf("\n")) >= 0) {
    const line = buffer.slice(0, i).trim();
    buffer = buffer.slice(i + 1);
    if (!line) continue;
    try { handleMessage(JSON.parse(line)); } catch (e) { /* malformed line */ }
  }
});
process.stdin.on("close", () => process.exit(0));
