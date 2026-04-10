#!/usr/bin/env node
/**
 * Session-persistence smoke test for Pathfinder MCP servers.
 *
 * Usage:
 *   node scripts/test-session-persistence.js <base-url> <bearer-token>
 *   node scripts/test-session-persistence.js https://toggl.mcp.pathfindermarketing.com.au $MCP_TOGGL_TOKEN
 *
 * Exits 0 on all assertions passing, 1 otherwise.
 *
 * Asserts the three regressions that the "session resurrection" bug
 * (see PM-Labs/mcp-playwright@1d75780) introduces:
 *   1. A session id must survive a follow-up request (persistence).
 *   2. An unknown session id must yield HTTP 404, not a silently remapped 200.
 *   3. The server must NOT rewrite the session id mid-conversation.
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
  // --- Assertion 1: initialize returns a session id ---
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
  if (!sessionId) {
    fail('initialize did not set Mcp-Session-Id header', init.text.slice(0, 500));
  }
  pass(`initialize -> session ${sessionId.slice(0, 8)}...`);

  // Some servers require an 'initialized' notification before tools/list
  await postJson(
    { jsonrpc: '2.0', method: 'notifications/initialized' },
    { 'mcp-session-id': sessionId }
  );

  // --- Assertion 2: tools/list with the real session id must succeed AND not rewrite the id ---
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

  // --- Assertion 3: unknown session id must return 404 ---
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

  console.log('\nAll session-persistence assertions passed.');
})().catch((err) => {
  console.error('ERROR:', err);
  process.exit(1);
});
