# Garmin training dashboard

Cloud build source for the password-protected dashboard published at
`https://garmin-vijesh.pages.dev/`.

## Cloudflare Pages

- Build command: `python cloud_build.py`
- Build output directory: `dist`
- Production branch: `main`
- Required encrypted build secret: `GARMIN_PERSONAL_API_KEY`
- Runtime secrets: `DASHBOARD_PASSWORD_HASH` and `DEPLOY_HOOK_URL`

The build downloads Garmin data only into the ephemeral build environment.
Downloaded JSON, tokens, the generated dashboard, and the generated Worker are
ignored by Git and must never be committed.

