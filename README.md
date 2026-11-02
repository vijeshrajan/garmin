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

