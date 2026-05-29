/**
 * Secondary Brain — edge API proxy + auth gate
 *
 * kia.aetherahealthcare.com/api/* and /health route here. Cloudflare Access is
 * BYPASSED on these paths so it never 302-redirects an XHR; this Worker instead
 * validates the Cloudflare Access session JWT (CF_Authorization cookie) against
 * the team JWKS and returns a clean 401 when unauthenticated. /health is public.
 * Authenticated requests are forwarded over the Tunnel to the local backend,
 * reaching the locked origin with an Access service token.
 */

const ACCESS_AUDS = [
  "0b5343b0a6d3ecf2391a4de18da6f0285d977ef59407b6865865bfb1fcf984e0", // kia root (SPA login)
  "d4c828f04e9657a7540eeefab158317d33301e6a11a81eaccf88b5b58b7c2a0b", // kia /api (bypass)
  "e2128d7a6b5031331878b9595b17f066c33a2a8619c61b256dcf0516f1372fe3", // kia /health (bypass)
  "e4e16512e7ac821b88ae0a91ba24e899efef1fd248c22cfdbadec78596c2a381", // origin tunnel
];
const ACCESS_ISS = "https://aetheraonline.cloudflareaccess.com";
const ACCESS_TEAM_DOMAIN = "aetheraonline.cloudflareaccess.com";

const HOP_BY_HOP = new Set([
  "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "te", "trailer", "transfer-encoding", "upgrade", "content-length", "host",
]);

let _jwks = null;
let _jwksAt = 0;

export default {
  async fetch(request, env) {
    try {
      const url = new URL(request.url);

      if (request.method === "OPTIONS") {
        return new Response(null, { status: 204, headers: corsHeaders(env) });
      }

      const isHealth = url.pathname === "/health" || url.pathname.startsWith("/health/");

      let userEmail = null;
      if (!isHealth) {
        const cookieHeader = request.headers.get("Cookie") || "";
        const cookieNames = cookieHeader.split(";").map((c) => c.split("=")[0].trim()).filter(Boolean);
        const token = getAccessToken(request);
        const res = token ? await verifyAccessJwt(token) : { ok: false, reason: "no_token" };
        if (!res.ok) {
          return json(
            { error: "unauthorized", reason: res.reason, cookies_seen: cookieNames, token_aud: res.aud || null },
            401,
            env
          );
        }
        userEmail = res.payload.email || null;
      }

      const origin = (env.BACKEND_ORIGIN || "").replace(/\/$/, "");
      if (!origin) return json({ error: "BACKEND_ORIGIN not configured" }, 500, env);
      const upstreamUrl = origin + url.pathname + url.search;

      const headers = new Headers();
      // copy a safe subset of inbound headers
      for (const [k, v] of request.headers) {
        if (!HOP_BY_HOP.has(k.toLowerCase())) headers.set(k, v);
      }
      headers.set("Host", new URL(origin).host);
      if (userEmail) headers.set("x-auth-user", userEmail);
      if (env.CF_ACCESS_CLIENT_ID && env.CF_ACCESS_CLIENT_SECRET) {
        headers.set("CF-Access-Client-Id", env.CF_ACCESS_CLIENT_ID);
        headers.set("CF-Access-Client-Secret", env.CF_ACCESS_CLIENT_SECRET);
      }

      // Buffer the request body (avoids streaming/duplex issues that 502 on POST).
      let body;
      if (!["GET", "HEAD"].includes(request.method)) {
        body = await request.arrayBuffer();
      }

      let resp;
      try {
        resp = await fetch(upstreamUrl, { method: request.method, headers, body, redirect: "manual" });
      } catch (err) {
        return json({ error: "upstream_unreachable", detail: String(err) }, 502, env);
      }

      // Buffer the upstream response too, then return — avoids stream-delivery 520s.
      const buf = await resp.arrayBuffer();
      const outHeaders = new Headers();
      for (const [k, v] of resp.headers) {
        if (!HOP_BY_HOP.has(k.toLowerCase()) && k.toLowerCase() !== "content-encoding") {
          outHeaders.set(k, v);
        }
      }
      for (const [k, v] of Object.entries(corsHeaders(env))) outHeaders.set(k, v);
      outHeaders.set("X-Content-Type-Options", "nosniff");
      outHeaders.set("Referrer-Policy", "strict-origin-when-cross-origin");
      return new Response(buf, { status: resp.status, statusText: resp.statusText, headers: outHeaders });
    } catch (e) {
      return new Response(JSON.stringify({ error: "worker_exception", detail: String(e) }), {
        status: 500,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*" },
      });
    }
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
    if (parts.length !== 3) return { ok: false, reason: "malformed_token" };
    const [h, p, sig] = parts;
    const header = JSON.parse(new TextDecoder().decode(b64url(h)));
    const payload = JSON.parse(new TextDecoder().decode(b64url(p)));
    const auds = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
    if (!payload.exp || payload.exp * 1000 < Date.now()) return { ok: false, reason: "expired", aud: auds };
    if (payload.iss && payload.iss !== ACCESS_ISS) return { ok: false, reason: "iss_mismatch", aud: auds };
    if (!auds.some((a) => ACCESS_AUDS.includes(a))) return { ok: false, reason: "aud_mismatch", aud: auds };
    const jwk = (await getJwks()).find((k) => k.kid === header.kid);
    if (!jwk) return { ok: false, reason: "no_jwk_for_kid", aud: auds };
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
    return ok ? { ok: true, payload } : { ok: false, reason: "bad_signature", aud: auds };
  } catch (e) {
    return { ok: false, reason: "parse_error: " + String(e) };
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
