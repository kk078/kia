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

// --- Tier A cloud failover -------------------------------------------------
// When the local KIA backend (reached over the Tunnel) is unreachable or the
// edge can't get a healthy response, these chat-type endpoints fail over to
// Ollama Cloud directly so KIA keeps answering. Degraded mode means no local
// knowledge base, memory, or /build — just the cloud LLM with KIA's persona.
const CHAT_STREAM_PATH = "/api/v1/chat/stream";
const GENERATE_PATH = "/api/v1/llm/generate";
const RAG_PATH = "/api/v1/knowledge/rag";
const FAILOVER_PATHS = new Set([CHAT_STREAM_PATH, GENERATE_PATH, RAG_PATH]);
// Origin-down signatures: fetch threw, or Cloudflare/origin returned one of these.
const FAILOVER_STATUSES = new Set([502, 503, 504, 520, 521, 522, 523, 524, 525, 530]);

const KIA_PERSONA =
  "You are KIA (Kiran's Intelligence Architecture), a personal AI assistant and " +
  "coding companion. You are KIA — not Llama, Qwen, or any generic base model; when " +
  "asked who you are, identify as KIA. Be precise, direct, and practical. When asked " +
  "for code, return correct, runnable code with minimal prose.";
const FAILOVER_NOTE =
  " NOTE: You are currently running in CLOUD-FAILOVER mode because Kiran's local " +
  "machine is unreachable. You do NOT have access to his private knowledge base, " +
  "memory, or the ability to run commands. Answer from general knowledge, and if " +
  "asked about personal/local/indexed data, say it's offline until the local backend reconnects.";

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

      const failoverEligible = FAILOVER_PATHS.has(url.pathname);

      let resp;
      try {
        resp = await fetch(upstreamUrl, { method: request.method, headers, body, redirect: "manual" });
      } catch (err) {
        if (failoverEligible) {
          const fo = await cloudFailover(url, env, body);
          if (fo) return fo;
        }
        if (isHealth) return healthDegraded(env);
        return json({ error: "upstream_unreachable", detail: String(err) }, 502, env);
      }

      // Origin reachable but unhealthy (tunnel up, backend down) → same failover.
      if (FAILOVER_STATUSES.has(resp.status)) {
        if (failoverEligible) {
          const fo = await cloudFailover(url, env, body);
          if (fo) return fo;
        }
        if (isHealth) return healthDegraded(env);
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

// Synthetic health for the public /health path when the local backend is down,
// so the dashboard/banner reflect cloud-failover mode instead of a hard error.
function healthDegraded(env) {
  return json(
    {
      status: "degraded",
      mode: "cloud-failover",
      reasons: [
        "Local KIA backend unreachable — running on Ollama Cloud failover. " +
          "Knowledge base, memory, and /build are offline until it reconnects.",
      ],
      components: {
        local_backend: { status: "down" },
        cloud_failover: { status: "up" },
      },
    },
    200,
    env
  );
}

// Route a failover-eligible request to Ollama Cloud. Returns a Response on
// success, or null if failover isn't possible (no key / cloud also failed) so
// the caller can surface the original error.
async function cloudFailover(url, env, bufferedBody) {
  const apiKey = env.OLLAMA_CLOUD_API_KEY;
  if (!apiKey) return null;
  const base = (env.OLLAMA_CLOUD_URL || "https://ollama.com/v1").replace(/\/$/, "");
  const model = env.OLLAMA_CLOUD_MODEL || "gpt-oss:120b";
  const sys = KIA_PERSONA + FAILOVER_NOTE;

  if (url.pathname === CHAT_STREAM_PATH) {
    let payload = {};
    try {
      payload = JSON.parse(new TextDecoder().decode(bufferedBody));
    } catch {
      payload = {};
    }
    const messages = [
      { role: "system", content: sys },
      { role: "user", content: payload.message || "" },
    ];
    return streamFailover(base, model, apiKey, messages, payload.conversation_id || null, env);
  }

  if (url.pathname === GENERATE_PATH) {
    const text = await cloudComplete(base, model, apiKey, sys, url.searchParams.get("prompt") || "");
    if (text == null) return null;
    return json({ response: text, degraded: "cloud failover — local KIA unreachable" }, 200, env);
  }

  if (url.pathname === RAG_PATH) {
    const text = await cloudComplete(base, model, apiKey, sys, url.searchParams.get("question") || "");
    if (text == null) return null;
    return json(
      { answer: text, degraded: "cloud failover — answered without your knowledge base" },
      200,
      env
    );
  }
  return null;
}

// Non-streaming Ollama Cloud completion. Returns the text, or null on failure.
async function cloudComplete(base, model, apiKey, system, prompt) {
  try {
    const r = await fetch(base + "/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: system },
          { role: "user", content: prompt },
        ],
        stream: false,
      }),
    });
    if (!r.ok) return null;
    const j = await r.json();
    const text = j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content;
    return text == null ? null : text;
  } catch {
    return null;
  }
}

// Stream from Ollama Cloud, translating OpenAI SSE deltas into KIA's SSE event
// contract (meta → token… → done → [DONE]) with degraded markers throughout.
function streamFailover(base, model, apiKey, messages, convId, env) {
  const enc = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const sse = (obj) => controller.enqueue(enc.encode(`data: ${JSON.stringify(obj)}\n\n`));
      sse({ type: "meta", conversation_id: convId, degraded: true, mode: "cloud-failover" });
      try {
        const r = await fetch(base + "/chat/completions", {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
          body: JSON.stringify({ model, messages, stream: true }),
        });
        if (!r.ok || !r.body) {
          sse({ type: "token", content: `\n\n[KIA cloud-failover error: HTTP ${r.status}]` });
        } else {
          const reader = r.body.getReader();
          const dec = new TextDecoder();
          let buf = "";
          for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            buf += dec.decode(value, { stream: true });
            const lines = buf.split("\n");
            buf = lines.pop();
            for (const line of lines) {
              const s = line.trim();
              if (!s.startsWith("data:")) continue;
              const data = s.slice(5).trim();
              if (!data || data === "[DONE]") continue;
              try {
                const j = JSON.parse(data);
                const delta = j.choices && j.choices[0] && j.choices[0].delta && j.choices[0].delta.content;
                if (delta) sse({ type: "token", content: delta });
              } catch {
                /* ignore keep-alive / partial */
              }
            }
          }
        }
      } catch (e) {
        sse({ type: "token", content: `\n\n[KIA cloud-failover error: ${String(e)}]` });
      }
      sse({ type: "done", conversation_id: convId, model: `${model} (cloud-failover)`, degraded: true });
      controller.enqueue(enc.encode("data: [DONE]\n\n"));
      controller.close();
    },
  });
  const headers = new Headers({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
  });
  for (const [k, v] of Object.entries(corsHeaders(env))) headers.set(k, v);
  return new Response(stream, { status: 200, headers });
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
