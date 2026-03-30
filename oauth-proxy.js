const http = require("http");
const { createHash, randomUUID } = require("crypto");
const { URL } = require("url");

const PORT = parseInt(process.env.PORT || "8080", 10);
const BACKEND_PORT = parseInt(process.env.BACKEND_PORT || "8081", 10);
const AUTH_TOKEN = (process.env.MCP_AUTH_TOKEN || "").trim();
const OAUTH_CLIENT_ID = (process.env.OAUTH_CLIENT_ID || "").trim();
const OAUTH_CLIENT_SECRET = (process.env.OAUTH_CLIENT_SECRET || "").trim();

const authCodes = {};
const sessionMap = new Map();
const SESSION_MAP_MAX = 100;

function parseBody(req) {
  return new Promise((resolve) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const raw = Buffer.concat(chunks).toString();
      const ct = req.headers["content-type"] || "";
      if (ct.includes("application/json")) {
        try { resolve(JSON.parse(raw)); } catch { resolve(raw); }
      } else if (ct.includes("urlencoded")) {
        resolve(Object.fromEntries(new URLSearchParams(raw)));
      } else { resolve(raw); }
    });
  });
}

function sendJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) });
  res.end(body);
}

function proxy(req, res, bodyBuf) {
  let sessionId = req.headers["mcp-session-id"];
  if (sessionId && sessionMap.has(sessionId)) {
    const mapped = sessionMap.get(sessionId);
    req.headers["mcp-session-id"] = mapped;
    console.log("[SESSION] Remapped stale " + sessionId + " -> " + mapped);
    sessionId = mapped;
  }
  const headers = { ...req.headers, host: "localhost:" + BACKEND_PORT };
  delete headers["content-length"];
  if (bodyBuf) headers["content-length"] = bodyBuf.length;
  const proxyReq = http.request(
    { hostname: "127.0.0.1", port: BACKEND_PORT, path: req.url, method: req.method, headers },
    (proxyRes) => {
      const newSid = proxyRes.headers["mcp-session-id"];
      if (newSid && sessionId && newSid !== sessionId) {
        if (sessionMap.size >= SESSION_MAP_MAX) { const o = sessionMap.keys().next().value; sessionMap.delete(o); }
        sessionMap.set(sessionId, newSid);
      }
      if ((proxyRes.statusCode === 404 || proxyRes.statusCode === 400) && sessionId) {
        delete req.headers["mcp-session-id"];
        proxy(req, res, bodyBuf);
        return;
      }
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res);
    }
  );
  proxyReq.on("error", (e) => { console.error("[PROXY] Backend error:", e.message); sendJson(res, 502, { error: "backend_unavailable" }); });
  if (bodyBuf) proxyReq.write(bodyBuf);
  proxyReq.end();
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost:" + PORT);
  const path = url.pathname;
  if (path === "/health") return sendJson(res, 200, { status: "ok" });
  if (path === "/.well-known/oauth-protected-resource") {
    const base = "https://" + req.headers.host;
    return sendJson(res, 200, { resource: base + "/mcp", authorization_servers: [base] });
  }
  if (path === "/.well-known/oauth-authorization-server") {
    const base = "https://" + req.headers.host;
    return sendJson(res, 200, { issuer: base, authorization_endpoint: base + "/authorize", token_endpoint: base + "/oauth/token", grant_types_supported: ["authorization_code", "client_credentials"], code_challenge_methods_supported: ["S256"], response_types_supported: ["code"] });
  }
  if (path === "/authorize" && req.method === "GET") {
    const p = url.searchParams;
    if (p.get("client_id") !== OAUTH_CLIENT_ID) return sendJson(res, 401, { error: "invalid_client" });
    if (p.get("response_type") !== "code") return sendJson(res, 400, { error: "unsupported_response_type" });
    if (!p.get("code_challenge")) return sendJson(res, 400, { error: "code_challenge required" });
    const code = randomUUID();
    authCodes[code] = { codeChallenge: p.get("code_challenge"), codeChallengeMethod: p.get("code_challenge_method") || "S256", redirectUri: p.get("redirect_uri"), expiresAt: Date.now() + 5 * 60 * 1000 };
    const redir = new URL(p.get("redirect_uri"));
    redir.searchParams.set("code", code);
    if (p.get("state")) redir.searchParams.set("state", p.get("state"));
    res.writeHead(302, { Location: redir.toString() });
    return res.end();
  }
  if (path === "/oauth/token" && req.method === "POST") {
    const body = await parseBody(req);
    if (body.grant_type === "authorization_code") {
      const stored = authCodes[body.code];
      if (!stored || stored.expiresAt < Date.now()) return sendJson(res, 400, { error: "invalid_grant" });
      const expected = createHash("sha256").update(body.code_verifier).digest("base64url");
      if (expected !== stored.codeChallenge) return sendJson(res, 400, { error: "invalid_grant" });
      if (body.redirect_uri && body.redirect_uri !== stored.redirectUri) return sendJson(res, 400, { error: "invalid_grant" });
      delete authCodes[body.code];
      return sendJson(res, 200, { access_token: AUTH_TOKEN, token_type: "Bearer", expires_in: 86400 });
    }
    let cid, csec;
    const ba = req.headers["authorization"];
    if (ba && ba.startsWith("Basic ")) {
      const decoded = Buffer.from(ba.slice(6), "base64").toString();
      const colon = decoded.indexOf(":");
      cid = decoded.slice(0, colon); csec = decoded.slice(colon + 1);
    } else { cid = body.client_id; csec = body.client_secret; }
    if (cid !== OAUTH_CLIENT_ID || csec !== OAUTH_CLIENT_SECRET) return sendJson(res, 401, { error: "invalid_client" });
    return sendJson(res, 200, { access_token: AUTH_TOKEN, token_type: "Bearer", expires_in: 86400 });
  }
  if (path === "/mcp" || path.startsWith("/mcp/")) {
    if (AUTH_TOKEN) {
      const ah = req.headers["authorization"];
      if (!ah || !ah.startsWith("Bearer ")) {
        res.writeHead(401, { "WWW-Authenticate": "Bearer resource_metadata=\"https://" + req.headers.host + "/.well-known/oauth-protected-resource\"", "Content-Type": "application/json" });
        return res.end(JSON.stringify({ error: "Unauthorized" }));
      }
      if (ah.slice(7) !== AUTH_TOKEN) {
        res.writeHead(401, { "WWW-Authenticate": "Bearer error=\"invalid_token\"", "Content-Type": "application/json" });
        return res.end(JSON.stringify({ error: "Unauthorized" }));
      }
    }
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => proxy(req, res, Buffer.concat(chunks)));
    return;
  }
  sendJson(res, 404, { error: "not_found" });
});

server.listen(PORT, "0.0.0.0", () => { console.log("OAuth proxy listening on :" + PORT + ", backend on :" + BACKEND_PORT); });
