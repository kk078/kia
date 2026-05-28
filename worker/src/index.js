/**
 * Secondary Brain — edge API proxy
 *
 * Sits in front of kia.aetherahealthcare.com/api/* and /health.
 * Forwards requests to the local backend (exposed via a Cloudflare Tunnel at
 * BACKEND_ORIGIN), injecting an Access service token so the origin can stay
 * locked behind Cloudflare Access. Adds CORS + security headers and an
 * optional KV-backed per-IP rate limit.
 *
 * Interactive user auth is handled by Cloudflare Access on the Pages app +
 * these Worker routes — this code does not implement login itself.
 */

const HOP_BY_HOP = new Set([
  "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "te", "trailer", "transfer-encoding", "upgrade",
]);

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(env) });
    }

    // Optional rate limiting (only if the RATE_LIMIT KV binding is configured)
    if (env.RATE_LIMIT) {
      const limited = await rateLimit(request, env);
      if (limited) {
        return json({ error: "rate_limited" }, 429, env);
      }
    }

    // Build the upstream request to the tunnel-backed origin.
    const origin = (env.BACKEND_ORIGIN || "").replace(/\/$/, "");
    if (!origin) {
      return json({ error: "BACKEND_ORIGIN not configured" }, 500, env);
    }
    const upstreamUrl = origin + url.pathname + url.search;

    const headers = new Headers(request.headers);
    for (const h of HOP_BY_HOP) headers.delete(h);
    headers.set("Host", new URL(origin).host);

    // Inject Access service-token credentials so the origin accepts the call.
    if (env.CF_ACCESS_CLIENT_ID && env.CF_ACCESS_CLIENT_SECRET) {
      headers.set("CF-Access-Client-Id", env.CF_ACCESS_CLIENT_ID);
      headers.set("CF-Access-Client-Secret", env.CF_ACCESS_CLIENT_SECRET);
    }

    const init = {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "manual",
    };

    let resp;
    try {
      resp = await fetch(upstreamUrl, init);
    } catch (err) {
      return json({ error: "upstream_unreachable", detail: String(err) }, 502, env);
    }

    // Pass the response through with CORS + security headers attached.
    const outHeaders = new Headers(resp.headers);
    for (const h of HOP_BY_HOP) outHeaders.delete(h);
    const cors = corsHeaders(env);
    for (const [k, v] of Object.entries(cors)) outHeaders.set(k, v);
    outHeaders.set("X-Content-Type-Options", "nosniff");
    outHeaders.set("Referrer-Policy", "strict-origin-when-cross-origin");

    return new Response(resp.body, {
      status: resp.status,
      statusText: resp.statusText,
      headers: outHeaders,
    });
  },
};

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

async function rateLimit(request, env) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const limit = parseInt(env.RATE_LIMIT_PER_MIN || "120", 10);
  const windowKey = `rl:${ip}:${Math.floor(Date.now() / 60000)}`;
  const current = parseInt((await env.RATE_LIMIT.get(windowKey)) || "0", 10);
  if (current >= limit) return true;
  await env.RATE_LIMIT.put(windowKey, String(current + 1), { expirationTtl: 90 });
  return false;
}
