"""Package the generated dashboard as a password-protected Cloudflare Worker.

The Garmin API key and raw JSON never enter the Worker.  Only the already-rendered
dashboard HTML is embedded in the deployment artifact.
"""
from __future__ import annotations

import base64
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "dashboard.html"
OUTPUT = ROOT / "data" / "cloudflare_worker.js"


dashboard_b64 = base64.b64encode(SOURCE.read_bytes()).decode("ascii")
worker = f'''const DASHBOARD_B64 = "{dashboard_b64}";
const encoder = new TextEncoder();

function dashboardHtml() {{
  const bytes = Uint8Array.from(atob(DASHBOARD_B64), c => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}}

async function passwordHash(password) {{
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(password));
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}}

function safeEqual(left, right) {{
  if (!left || !right || left.length !== right.length) return false;
  let result = 0;
  for (let index = 0; index < left.length; index++) result |= left.charCodeAt(index) ^ right.charCodeAt(index);
  return result === 0;
}}

async function isAuthorized(request, env) {{
  const header = request.headers.get("Authorization") || "";
  if (!header.startsWith("Basic ")) return false;
  try {{
    const decoded = atob(header.slice(6));
    const separator = decoded.indexOf(":");
    if (separator < 0 || decoded.slice(0, separator) !== "vijesh") return false;
    const suppliedHash = await passwordHash(decoded.slice(separator + 1));
    return safeEqual(suppliedHash, env.DASHBOARD_PASSWORD_HASH);
  }} catch {{
    return false;
  }}
}}

const securityHeaders = {{
  "Cache-Control": "no-store",
  "Content-Security-Policy": "default-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY"
}};

export default {{
  async fetch(request, env) {{
    if (!(await isAuthorized(request, env))) {{
      return new Response("Sign in to view the private Garmin dashboard.", {{
        status: 401,
        headers: {{...securityHeaders, "WWW-Authenticate": 'Basic realm="Garmin Dashboard", charset="UTF-8"'}}
      }});
    }}

    const url = new URL(request.url);
    if (request.method === "POST" && url.pathname === "/api/refresh") {{
      if (!env.DEPLOY_HOOK_URL) {{
        return Response.json({{ok: false, message: "Cloud refresh is not configured yet."}}, {{status: 503, headers: securityHeaders}});
      }}
      const triggered = await fetch(env.DEPLOY_HOOK_URL, {{method: "POST"}});
      if (!triggered.ok) {{
        return Response.json({{ok: false, message: "Cloud refresh could not start. Try again shortly."}}, {{status: 502, headers: securityHeaders}});
      }}
      return Response.json({{ok: true, status: "accepted", message: "Cloud refresh started."}}, {{status: 202, headers: securityHeaders}});
    }}
    if (request.method === "GET" && (url.pathname === "/" || url.pathname === "/dashboard.html")) {{
      return new Response(dashboardHtml(), {{headers: {{...securityHeaders, "Content-Type": "text/html; charset=utf-8"}}}});
    }}
    if (request.method === "GET" && url.pathname === "/api/health") {{
      return Response.json({{ok: true}}, {{headers: securityHeaders}});
    }}
    if (request.method === "GET" && url.pathname === "/favicon.ico") {{
      return new Response(null, {{status: 204, headers: securityHeaders}});
    }}
    return new Response("Not found", {{status: 404, headers: securityHeaders}});
  }},

  async scheduled(_controller, env, ctx) {{
    if (!env.DEPLOY_HOOK_URL) return;
    ctx.waitUntil(
      fetch(env.DEPLOY_HOOK_URL, {{method: "POST"}}).then(response => {{
        if (!response.ok) throw new Error(`Scheduled cloud refresh failed: ${{response.status}}`);
      }})
    );
  }}
}};
'''

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(worker, encoding="utf-8")
print(f"Cloudflare Worker built: {OUTPUT}")

