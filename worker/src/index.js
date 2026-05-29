/**
 * Secondary Brain — edge API proxy + auth gate
 *
 * kia.aetherahealthcare.com/api/* and /health are routed here. Cloudflare Access
 * is BYPASSED on these paths (so it never 302-redirects an XHR, which browsers
 * can't follow cross-origin). Instead this Worker validates the Cloudflare Access
 * session JWT (the CF_Authorization cookie set when the user logs into the SPA)
 * against the team JWKS, returning a clean 401 JSON when unauthenticated.
 *
 * Authenticated requests are forwarded over the Cloudflare Tunnel to the local
 * backend; the locked origin is reached using an Access service token.
 */

const ACCESS_TEAM_DOMAIN = "aetheraonline.cloudflareaccess.com";
const ACCESS_AUD = "0b5343b0a6d3ecf2391a4de18da6f0285d977ef59407b6865865bfb1fcf984e0";

const HOP_BY_HOP = new Set([
  "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "te", "trailer", "transfer-encoding", "upgrade",
]);

let _jwks = null;
let _jwksAt = 0;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(env) });
    }

    const isHealth = url.pathname === "/health" || url.pathname.startsWith("/health/");

    let userEmail = null;
    if (!isHealth) {
      // Require a valid Access session for /api/*
      const token = getAccessToken(request);
      const payload = token ? await verifyAccessJwt(token) : null;
      if (!payload) {
        return json({ error: "unauthorized", detail: "No valid Cloudflare Access session." }, 401, env);
      }
      userEmail = payload.email || payload.identity_nonce || null;
    }

    const origin = (env.BACKEND_ORIGIN || "").replace(/\/$/, "");
    if (!origin) return json({ error: "BACKEND_ORIGIN not configured" }, 500, env);
    const upstreamUrl = origin + url.pathname + url.search;

    const headers = new Headers(request.headers);
    for (const h of HOP_BY_HOP) headers.delete(h);
    headers.set("Host", new URL(origin).host);
    if (userEmail) headers.set("x-auth-user", userEmail);
    if (env.CF_ACCESS_CLIENT_ID && env.CF_ACCESS_CLIENT_SECRET) {
      headers.set("CF-Access-Client-Id", env.CF_ACCESS_CLIENT_ID);
      headers.set("CF-Access-Client-Secret", env.CF_ACCESS_CLIENT_SECRET);
    }

    let resp;
    try {
      resp = await fetch(upstreamUrl, {
        method: request.method,
        headers,
        body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
        redirect: "manual",
      });
    } catch (err) {
      return json({ error: "upstream_unreachable", detail: String(err) }, 502, env);
    }

    const outHeaders = new Headers(resp.headers);
    for (const h of HOP_BY_HOP) outHeaders.delete(h);
    for (const [k, v] of Object.entries(corsHeaders(env))) outHeaders.set(k, v);
    outHeaders.set("X-Content-Type-Options", "nosniff");
    outHeaders.set("Referrer-Policy", "strict-origin-when-cross-origin");
    return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers: outHeaders });
  },
};

function getAccessToken(request) {
  const assertion = request.headers.get("cf-access-jwt-assertion");
  if (assertion) return assertion;
  const cookie = request.headers.get("Cookie") || "";
  const m = cookie.match(/(?:^|;\s*)CF_Authorization=([^;]+)/);
  return m ? m[1] : null;
}

async function getJwks() {
  const now = Date.now();
  if (_jwks && now - _jwksAt < 3600_000) return _jwks;
  const r = await fetch(`https://${ACCESS_TEAM_DOMAIN}/cdn-cgi/access/certs`);
  const j = await r.json();
  _jwks = j.keys || [];
  _jwksAt = now;
  return _jwks;
}

function b64url(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  const pad = s.length % 4 ? "=".repeat(4 - (s.length % 4)) : "";
  const bin = atob(s + pad);
  const u = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
  return u;
}

async function verifyAccessJwt(token) {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const [h, p, sig] = parts;
    const header = JSON.parse(new TextDecoder().decode(b64url(h)));
    const payload = JSON.parse(new TextDecoder().decode(b64url(p)));
    if (!payload.exp || payload.exp * 1000 < Date.now()) return null;
    const auds = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
    if (!auds.includes(ACCESS_AUD)) return null;
    const jwk = (await getJwks()).find((k) => k.kid === header.kid);
    if (!jwk) return null;
    const key = await crypto.subtle.importKey(
      "jwk",
      { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: "RS256", ext: true },
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
      false,
      ["verify"]
    );
    const ok = await crypto.subtle.verify(
      "RSASSA-PKCS1-v1_5",
      key,
      b64url(sig),
      new TextEncoder().encode(`${h}.${p}`)
    );
    return ok ? payload : null;
  } catch {
    return null;
  }
}

function corsHeaders(env) {
  return {
    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Credentials": "true",
    "Vary": "Origin",
  };
}

function json(obj, status, env) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(env) },
  });
}
