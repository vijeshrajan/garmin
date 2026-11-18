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
  "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; connect-src 'self'; img-src 'self' data:",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY"
}};

async function ensureSchema(env) {{
  if (!env.FITNESS_DB) return false;
  await env.FITNESS_DB.batch([
    env.FITNESS_DB.prepare("CREATE TABLE IF NOT EXISTS checkins(date TEXT PRIMARY KEY, body TEXT, sleep_felt TEXT, motivation INTEGER, time_available_min INTEGER, created_at TEXT)"),
    env.FITNESS_DB.prepare("CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, date TEXT, planned_session_id TEXT, location TEXT, status TEXT, session_rpe INTEGER, duration_min INTEGER, garmin_activity_id TEXT, notes TEXT)"),
    env.FITNESS_DB.prepare("CREATE TABLE IF NOT EXISTS sets(id TEXT PRIMARY KEY, session_id TEXT, date TEXT, exercise_id TEXT, set_no INTEGER, weight_kg REAL, reps INTEGER, rir INTEGER, estimated_1rm REAL)"),
    env.FITNESS_DB.prepare("CREATE TABLE IF NOT EXISTS body_measures(date TEXT PRIMARY KEY, weight_kg REAL, waist_cm REAL)")
  ]);
  return true;
}}

async function stateApi(request, env, url) {{
  if (!(await ensureSchema(env))) return Response.json({{checkin:null,sessions:[],sets:[],body:[]}}, {{headers:securityHeaders}});
  if (request.method === "GET" && url.pathname === "/api/state") {{
    const date = url.searchParams.get("date") || "";
    const [checkin, sessions, sets, body] = await env.FITNESS_DB.batch([
      env.FITNESS_DB.prepare("SELECT * FROM checkins WHERE date = ?").bind(date),
      env.FITNESS_DB.prepare("SELECT * FROM sessions ORDER BY date DESC LIMIT 100"),
      env.FITNESS_DB.prepare("SELECT * FROM sets ORDER BY date DESC, set_no ASC LIMIT 1000"),
      env.FITNESS_DB.prepare("SELECT * FROM body_measures ORDER BY date DESC LIMIT 100")
    ]);
    return Response.json({{checkin:checkin.results[0]||null,sessions:sessions.results,sets:sets.results,body:body.results}}, {{headers:securityHeaders}});
  }}
  const payload = await request.json();
  if (request.method === "POST" && url.pathname === "/api/checkin") {{
    await env.FITNESS_DB.prepare("INSERT INTO checkins(date,body,sleep_felt,motivation,time_available_min,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(date) DO UPDATE SET body=excluded.body,sleep_felt=excluded.sleep_felt,motivation=excluded.motivation,time_available_min=excluded.time_available_min,created_at=excluded.created_at").bind(payload.date,payload.body,payload.sleep_felt,payload.motivation,payload.time_available_min,new Date().toISOString()).run();
    return Response.json({{ok:true}}, {{headers:securityHeaders}});
  }}
  if (request.method === "POST" && url.pathname === "/api/session") {{
    const session = payload.session || {{}};
    const statements = [env.FITNESS_DB.prepare("INSERT INTO sessions(id,date,planned_session_id,location,status,session_rpe,duration_min,garmin_activity_id,notes) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET location=excluded.location,status=excluded.status,session_rpe=excluded.session_rpe,duration_min=excluded.duration_min,notes=excluded.notes").bind(session.id,session.date,session.planned_session_id,session.location,session.status,session.session_rpe,session.duration_min,session.garmin_activity_id||null,session.notes||null),env.FITNESS_DB.prepare("DELETE FROM sets WHERE session_id = ?").bind(session.id)];
    for (const set of payload.sets || []) statements.push(env.FITNESS_DB.prepare("INSERT INTO sets(id,session_id,date,exercise_id,set_no,weight_kg,reps,rir,estimated_1rm) VALUES(?,?,?,?,?,?,?,?,?)").bind(set.id,set.session_id,set.date,set.exercise_id,set.set_no,set.weight_kg,set.reps,set.rir,set.estimated_1rm));
    await env.FITNESS_DB.batch(statements);
    return Response.json({{ok:true}}, {{headers:securityHeaders}});
  }}
  if (request.method === "POST" && url.pathname === "/api/body") {{
    await env.FITNESS_DB.prepare("INSERT INTO body_measures(date,weight_kg,waist_cm) VALUES(?,?,?) ON CONFLICT(date) DO UPDATE SET weight_kg=excluded.weight_kg,waist_cm=excluded.waist_cm").bind(payload.date,payload.weight_kg||null,payload.waist_cm||null).run();
    return Response.json({{ok:true}}, {{headers:securityHeaders}});
  }}
  return new Response("Not found", {{status:404,headers:securityHeaders}});
}}

export default {{
  async fetch(request, env) {{
    if (!(await isAuthorized(request, env))) {{
      return new Response("Sign in to view the private Garmin dashboard.", {{
        status: 401,
        headers: {{...securityHeaders, "WWW-Authenticate": 'Basic realm="Garmin Dashboard", charset="UTF-8"'}}
      }});
    }}

    const url = new URL(request.url);
    if (url.pathname === "/api/state" || url.pathname === "/api/checkin" || url.pathname === "/api/session" || url.pathname === "/api/body") {{
      return stateApi(request, env, url);
    }}
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

