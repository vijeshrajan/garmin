# Garmin training dashboard

Cloud build source for the password-protected dashboard published at
`https://garmin-vijesh.pages.dev/`.

## Cloudflare Workers Builds

- Build command: `python cloud_build.py`
- Deploy command: `npx wrangler deploy`
- Production branch: `main`
- Required encrypted build secret: `GARMIN_PERSONAL_API_KEY`
- Runtime secrets: `DASHBOARD_PASSWORD_HASH` and `DEPLOY_HOOK_URL`

The Worker runs a UTC cron trigger at `0 */2 * * *` and starts a fresh cloud
build through its deploy hook. The dashboard Refresh button starts the same
cloud build, so neither refresh path depends on the laptop.

The build downloads Garmin data only into the ephemeral build environment.
Downloaded JSON, tokens, the generated dashboard, and the generated Worker are
ignored by Git and must never be committed.

## Advisor interface

The generated dashboard is organized into Today, This week, Recovery, Progress,
and Insights & evidence. `advisor_ui.py`, `advisor.css`, and `advisor.js` assemble
the decision-first layout after the existing data calculations. The daily
check-in changes the current tab only; it is not saved or sent to a server.

Daily guidance is a transparent heuristic, not Garmin Training Readiness or a
clinically validated model. It withholds intensity guidance when recovery
records are dated or sparse. Current vital cards repeat the same recommendation
as the headline. Progress distinguishes a recent 90-day running benchmark from
historical endurance records and does not infer a probability of marathon success.
Chart windows use actual calendar spacing and include keyboard-readable points.

Run `python -m unittest test_advisor.py` for absent-data, stale-data and
conflicting-signal regression checks, and `node --check advisor.js` for syntax.

Next development priorities: durable goals and daily context, planned-versus-done
training, progressive strength logging, comparable-session analysis, and an
experiment log with outcome reviews. Any future language model should explain
verified calculations and cite their dates, rather than invent measurements or
override symptom rules.

