#!/usr/bin/env node
"use strict";
/**
 * Protocol test for the computer-use MCP server.
 * Feeds JSON-RPC messages over stdio and asserts the MCP contract.
 * CDP-dependent tools are exercised for GRACEFUL FAILURE (no browser in CI);
 * with a live CDP endpoint (set CDP_PORT) they would succeed.
 *
 *   node tests/mcp/server.test.js
 */
const { spawn } = require("child_process");
const path = require("path");
const assert = require("assert");

const SERVER = path.join(__dirname, "..", "..", "mcp", "server", "server.js");
const proc = spawn(process.execPath, [SERVER], {
  env: { ...process.env, CDP_PORT: process.env.CDP_PORT || "19999" }, // nothing listens here
  stdio: ["pipe", "pipe", "inherit"],
});

let id = 0;
const pending = new Map();
let buf = "";
proc.stdout.on("data", (chunk) => {
  buf += chunk.toString();
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (!line) continue;
    const msg = JSON.parse(line);
    if (msg.id != null && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
  }
});

function request(method, params) {
  const mid = ++id;
  return new Promise((resolve, reject) => {
    pending.set(mid, resolve);
    setTimeout(() => reject(new Error(`timeout waiting for ${method}`)), 8000);
    proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: mid, method, params }) + "\n");
  });
}

function notify(method, params) {
  proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", method, params }) + "\n");
}

const EXPECTED_TOOLS = 24;

(async () => {
  // 1. initialize
  const init = await request("initialize", {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: { name: "agentdrop-test", version: "0.0.0" },
  });
  assert.ok(init.result.serverInfo.name === "agentdrop-computer-use", "serverInfo");
  assert.ok(init.result.capabilities.tools, "tools capability");
  console.log("ok 1: initialize");
  notify("notifications/initialized", {});

  // 2. tools/list — 24 tools
  const list = await request("tools/list", {});
  assert.strictEqual(list.result.tools.length, EXPECTED_TOOLS,
    `expected ${EXPECTED_TOOLS} tools, got ${list.result.tools.length}`);
  const names = list.result.tools.map((t) => t.name);
  for (const required of ["computer_screenshot", "computer_click", "computer_type",
    "computer_scroll", "computer_wait", "computer_verify_change", "computer_detect_auth"]) {
    assert.ok(names.includes(required), `missing tool ${required}`);
  }
  for (const t of list.result.tools) {
    assert.ok(t.inputSchema && t.inputSchema.type === "object", `${t.name} schema`);
    assert.ok(t.description && t.description.length > 10, `${t.name} description`);
  }
  console.log(`ok 2: tools/list -> ${list.result.tools.length} tools`);

  // 3. tools/call with a tool that needs CDP -> graceful error (no browser here)
  if (!process.env.CDP_PORT || process.env.CDP_PORT === "19999") {
    const shot = await request("tools/call", { name: "computer_screenshot", arguments: {} });
    assert.ok(shot.result.isError === true, "expected graceful CDP error");
    assert.ok(/no page target|failed|ECONNREFUSED/i.test(shot.result.content[0].text),
      `unexpected error text: ${shot.result.content[0].text}`);
    console.log("ok 3: CDP tool fails gracefully without a browser");
  } else {
    console.log("skip 3: live CDP endpoint configured");
  }

  // 4. unknown tool / unknown method errors
  const unknown = await request("tools/call", { name: "computer_fly", arguments: {} });
  assert.ok(unknown.error, "unknown tool error");
  const badMethod = await request("bogus/method", {});
  assert.ok(badMethod.error, "unknown method error");
  console.log("ok 4: error handling");

  proc.kill();
  console.log("\nMCP server protocol test PASSED");
  process.exit(0);
})().catch((e) => {
  console.error("MCP test FAILED:", e.message);
  proc.kill();
  process.exit(1);
});
