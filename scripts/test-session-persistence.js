#!/usr/bin/env node
/**
 * Session-persistence smoke test for Pathfinder MCP servers.
 *
 * Detects whether the server is running in stateful or stateless mode and
 * runs the appropriate assertion set. The bug this test guards against
 * (session resurrection — see PM-Labs/mcp-playwright@1d75780) only applies
 * to stateful servers; stateless servers cannot exhibit it.
 *
 * Usage:
 *   node scripts/test-session-persistence.js <base-url> <bearer-token>
 *   node scripts/test-session-persistence.js https://toggl.mcp.pathfindermarketing.com.au $MCP_TOGGL_TOKEN
 *
 * Exits 0 on all assertions passing, 1 otherwise.
 *
 * MODE DETECTION
 * --------------
 * After `initialize` returns 200, check for the `Mcp-Session-Id` response
 * header:
 *   - Present  → STATEFUL mode → run the 3 stateful assertions
 *   - Absent   → STATELESS mode → run the 2 stateless assertions
 *
 * STATEFUL ASSERTIONS
 * -------------------
 *   1. The session id from `initialize` must survive a follow-up `tools/list`
 *      request (basic persistence).
 *   2. The response `Mcp-Session-Id` header on the follow-up MUST equal the
 *      one we sent — i.e. the server must NOT rewrite the session id
 *      mid-conversation (the session-resurrection symptom).
 *   3. A `tools/list` request with a fabricated UUID session id MUST return
 *      HTTP 404 — the MCP-spec recovery signal. A 200 (silent remap) or
 *      400 ("Server not initialized" — fresh resurrected transport) is the
 *      session-resurrection regression.
 *
 * STATELESS ASSERTIONS
 * --------------------
 *   1. `tools/list` with no session header must return 200 (server processes
 *      requests independently).
 *   2. `tools/list` with a fabricated session header must NOT crash — return
 *      200 (header ignored, the common stateless behavior) or 404 (header
 *      acknowledged but rejected). Anything else (500, 502, hang) means the
 *      server is mishandling stateless requests.
 */
'use strict';

const { randomUUID } = require('crypto');

const [, , BASE_URL, TOKEN] = process.argv;
if (!BASE_URL || !TOKEN) {
  console.error('Usage: test-session-persistence.js <base-url> <bearer-token>');
  process.exit(2);
}

const MCP_URL = BASE_URL.replace(/\/+$/, '') + '/mcp';
const HEADERS_JSON = {
  'Content-Type': 'application/json',
  'Accept': 'application/json, text/event-stream',
  'Authorization': `Bearer ${TOKEN}`,
};

async function postJson(body, extraHeaders = {}) {
  const res = await fetch(MCP_URL, {
    method: 'POST',
    headers: { ...HEADERS_JSON, ...extraHeaders },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  return { status: res.status, headers: res.headers, text };
}

function fail(label, detail) {
  console.error(`FAIL: ${label}`);
  if (detail) console.error(detail);
  process.exit(1);
}

function pass(label) {
  console.log(`PASS: ${label}`);
}

(async () => {
  // --- Common: initialize must return 200 ---
  const init = await postJson({
    jsonrpc: '2.0',
    id: 1,
    method: 'initialize',
    params: {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: 'test-session-persistence', version: '1.0' },
    },
  });
  if (init.status !== 200) {
    fail('initialize returned non-200', `status=${init.status} body=${init.text.slice(0, 500)}`);
  }

  const sessionId = init.headers.get('mcp-session-id');

  // --- Mode detection ---
  if (sessionId) {
    // ============== STATEFUL MODE ==============
    pass(`initialize -> session ${sessionId.slice(0, 8)}... (mode: STATEFUL)`);

    // Some servers require an 'initialized' notification before tools/list
    await postJson(
      { jsonrpc: '2.0', method: 'notifications/initialized' },
      { 'mcp-session-id': sessionId }
    );

    // --- Stateful assertion 1+2: tools/list persists session id without rewrite ---
    const list = await postJson(
      { jsonrpc: '2.0', id: 2, method: 'tools/list' },
      { 'mcp-session-id': sessionId }
    );
    if (list.status !== 200) {
      fail('tools/list on active session returned non-200', `status=${list.status} body=${list.text.slice(0, 500)}`);
    }
    const returnedId = list.headers.get('mcp-session-id');
    if (returnedId && returnedId !== sessionId) {
      fail(
        'server rewrote session id mid-conversation (session resurrection regression)',
        `sent=${sessionId} received=${returnedId}`
      );
    }
    pass('tools/list persisted session id (no rewrite)');

    // --- Stateful assertion 3: unknown session id must return 404 ---
    const bogus = randomUUID();
    const unknown = await postJson(
      { jsonrpc: '2.0', id: 3, method: 'tools/list' },
      { 'mcp-session-id': bogus }
    );
    if (unknown.status !== 404) {
      fail(
        'unknown session id did not return 404 (session resurrection regression)',
        `status=${unknown.status} body=${unknown.text.slice(0, 500)}`
      );
    }
    pass('unknown session id -> 404');

    console.log('\nAll stateful session-persistence assertions passed.');
    return;
  }

  // ============== STATELESS MODE ==============
  pass('initialize -> 200 with no session header (mode: STATELESS)');

  // --- Stateless assertion 1: tools/list works without a session header ---
  const list = await postJson({ jsonrpc: '2.0', id: 2, method: 'tools/list' });
  if (list.status !== 200) {
    fail('stateless tools/list (no session header) returned non-200', `status=${list.status} body=${list.text.slice(0, 500)}`);
  }
  pass('tools/list (no session header) -> 200');

  // --- Stateless assertion 2: tools/list with a bogus session header is harmless ---
  const bogus = randomUUID();
  const withBogus = await postJson(
    { jsonrpc: '2.0', id: 3, method: 'tools/list' },
    { 'mcp-session-id': bogus }
  );
  if (withBogus.status !== 200 && withBogus.status !== 404) {
    fail(
      'stateless server mishandled bogus session header',
      `status=${withBogus.status} (expected 200 ignored or 404 rejected) body=${withBogus.text.slice(0, 500)}`
    );
  }
  pass(`tools/list with bogus session header -> ${withBogus.status} (acceptable)`);

  console.log('\nAll stateless assertions passed.');
})().catch((err) => {
  console.error('ERROR:', err);
  process.exit(1);
});
