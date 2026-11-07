# Aria → Garmin weight sync

## Goal

Automatically copy weigh-ins (weight + body fat %) from my **Fitbit Aria** scale into **Garmin Connect**, as soon as possible after I step off the scale. It will be self-hosted on my **Unraid** server.

This replaces **SmartScaleSync**, which stopped working when Google turned off the legacy Fitbit Web API.

## Background (researched Nov 2026)

### What broke
- Google turned off the legacy **Fitbit Web API** and Fitbit OAuth on **2 Nov 2026**. Requests now return `HTTP 410 Gone`.
- The replacement is the **Google Health API** (`https://health.googleapis.com/v4/...`), using Google OAuth 2.0.
  - It supports reading and writing **Weight** and **Body Fat**. They are separate data types (`weight`, `body-fat`), so a weigh-in arrives as two records.
  - Scope: `https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly`
  - Data endpoint pattern: `GET /v4/users/me/dataTypes/{data-type}/dataPoints?filter=...` (filter syntax is SQL-WHERE-like, e.g. on `start_time`)
  - **Webhooks: confirmed for `weight` and `body-fat`** (28 data types supported; checked 5 Nov 2026 at https://developers.google.com/health/api/webhooks). See "Webhook details" below.
  - Existing Fitbit tokens don't carry over, so I'll need to give consent again through Google OAuth.

### Why Garmin's new Personal API doesn't help
- Garmin launched free **Personal API keys** on 21 Oct 2026 (Garmin Connect web → Settings → Personal API Key).
- It is **read-only (pull-only)**. Its scopes are `CONNECT_READ`, `PERSONAL_API_*_READ`, so it **cannot post weigh-ins**.
- The write path has to be **unofficial**: a library that logs in as me, the way the mobile app does.

## Architecture

```
Aria --wifi--> Fitbit/Google cloud --(poll or webhook)--> sync service --> Garmin Connect
                                 Google Health API              unofficial lib (weigh-in / FIT weight-scale file)
```

### Fitbit side: Google Health API
- Create a Google Cloud project, enable the Google Health API, and create an OAuth client (Web server; redirect URI can be `https://www.google.com` for manual code copy, or a local callback).
- Consent screen: **User type = External**. Add my **personal Google account** (the one holding the Fitbit data) as a test user.
  - The Cloud project can be owned by my business Workspace account **or** my personal account. That doesn't affect token expiry.
  - Don't use **Internal**: only Workspace org users could authorise, and my personal account couldn't sign in.
- **Token expiry:**
  - In **Testing** status, refresh tokens expire after **7 days**.
  - In **In production** status, refresh tokens generally don't expire (unless revoked or unused for about 6 months).
  - Unverified clients are capped at 100 users in *both* testing and production. Plan: **publish to production unverified** (one user) and click through the "unverified app" warning once.
  - ⚠️ To verify: that Google allows restricted Health scopes in an unverified production app. If not, the fallback is Testing mode with a weekly re-consent, plus an alert when the token expires.
- Request with `access_type=offline` (and `prompt=consent` the first time) to get a refresh token.
- Helper library option: `fitbitApp` v2.x on PyPI (Google Health API wrapper, OAuth with auto-refresh, personal use). Or just call the REST API directly with `google-auth` / `requests`.

### Garmin side: unofficial write
Candidate libraries:
1. **python-garminconnect** (`pip install garminconnect curl_cffi`, Python 3.12+), the most widely used. It has body composition / weigh-in methods (e.g. `add_body_composition`, `add_weigh_in`; check the current names).
2. **garmin-connect-api** (`uv tool install garmin-connect-api`). It writes body composition as a **FIT weight-scale file**, the way Garmin Index scales do. It also has `garmin serve`, an HTTP API on `127.0.0.1:8765`, which is handy for Option A below.
3. **garmin-auth**, a wrapper around garminconnect that adds token persistence, MFA resume and rate-limit recovery.

**MFA / 2FA:** my Garmin account has email 2FA (it was needed for the heart/ECG feature).
- python-garminconnect handles MFA through a `prompt_mfa` callback (or `return_on_mfa=True` + `resume_login(code)`).
- After the first login it saves tokens to `~/.garminconnect/garmin_tokens.json` and refreshes them automatically. I only need to re-enter credentials and MFA if the refresh token expires or is revoked (password change, signing out all devices, Garmin changing its login flow).
- Plan: do the **first login interactively** in the container console, as the user the job runs as. The scheduled job then uses **only the saved tokens**, with no password and no MFA prompt. If the tokens are rejected, it fails loudly and alerts me instead of hanging.
- Treat the token file as a secret (the refresh token gives persistent account access). Keep it in a volume with `0600` permissions and don't store the Garmin password in env vars long-term.

## Latency: how fast can it sync?
- The Garmin upload takes seconds. The bottleneck is detecting the new reading.
- The Aria's own Wi-Fi upload to Fitbit is usually under a minute, and nothing can beat that.
- **Polling** every 5 minutes (optionally only during my usual weigh-in window) means about 5 minutes worst case. Simple, with nothing exposed to the internet. **Start here.**
- **Webhooks** (confirmed for weight and body fat) would be near-instant, but need a public HTTPS endpoint (Cloudflare Tunnel or Tailscale Funnel; no open ports). Add once polling works.

### Webhook details (from Google's docs)
- **Endpoint:** public HTTPS (TLS 1.2+). It must check the `Authorization` header against the secret set when creating the subscriber, and return **`204 No Content` quickly**; any other status or a timeout triggers a retry. Process the work asynchronously.
- **Verification handshake:** when a subscriber is created (or its endpoint/secret changes), Google sends two POSTs with User-Agent `Google-Health-API-Webhooks` and body `{"type": "verification"}`:
  1. With credentials: respond `200`/`201`.
  2. Without credentials: respond `401`/`403`.
  If either fails, subscriber creation fails with `FAILED_PRECONDITION`.
- **Payload is a pointer, not the data:** it contains `healthUserId`, `dataType`, `operation` (`UPSERT`/`DELETE`), affected `intervals` and sometimes a `recordId`. Then call the **`reconcile`** endpoint with a filter for each interval to fetch the actual values. Up to 99 notifications can arrive batched in one JSON array.
- **Signature:** each request has a `GOOGLE-HEALTH-API-SIGNATURE` header that can be checked against Google's published public keyset. Worth doing as well as checking the secret.
- **Scope:** notifications for weight need the user to have granted the health metrics scope (`googlehealth.health_metrics_and_measurements.readonly`).
- **Managing subscribers:** done through the `projects.subscribers` REST API. Use the Cloud **project number**, not the project ID, in the URL (the ID returns 400/403). A service account with a Google Health API role (Read/Editor/Admin) is recommended but optional; from a home lab, a service account key or my own gcloud credentials should work.
- **Handling `DELETE`:** decide whether deleting a weigh-in in Fitbit should delete it in Garmin too. Simplest is to ignore deletes and log them.
- **Polling is still needed as a safety net:** run a slower poll (e.g. hourly) to catch any missed webhooks, using the same dedup store.
- **Pair weight and body fat:** they arrive as separate records, so wait about 60–120 seconds after a new weight for the matching body-fat record, then upload one combined reading.
- **Idempotency:** store the IDs/timestamps already uploaded (SQLite) so retries never create duplicates in Garmin.

## Hosting options (Unraid), to explore

### Option A: n8n plus a small Garmin container (if I'm running n8n anyway)
- n8n: webhook trigger and cron trigger feeding the same flow, the Google OAuth2 credential (n8n handles refresh), dedup, the body-fat wait, failure alerts, and a visual execution history.
- Garmin container: `garmin-connect-api` running `garmin serve` (or a tiny FastAPI wrapper around python-garminconnect). It's on the internal Docker network only, and n8n calls it through an HTTP Request node.
- Why not do the Garmin side in n8n: there's no Garmin node, and the Code node can't easily use external Python packages without a custom image. It also keeps the fragile login code and tokens out of n8n.
- Downside: two moving parts. The first Garmin login happens in that container's console.

### Option B: a single Python container (if n8n isn't already in use)
- One script/service: poll Google Health, pair weight and body fat, dedup in SQLite, push to Garmin, and alert on failure (Unraid notification or phone push, e.g. ntfy/Pushover).
- A small Dockerfile plus an Unraid template (volumes for `/data` tokens and DB; env for poll interval and timezone `Pacific/Auckland`).
- Optional later: a small web server in the same container to receive Google webhooks.
- Fewer moving parts and easy to back up. Observability through logs and a "last synced" status.

**Recommendation:** use Option A if n8n already runs on Unraid; otherwise Option B. Either way, start with polling and add webhooks later.

### Decided (8 Nov 2026)
- **Option B**: a single Python container, no n8n.
- **Webhook ingress:** use **Unraid's built-in per-container Tailscale toggle** with **Funnel**. Don't use a Tailscale sidecar. Funnel exposes the whole container port, so the app's public port serves *only* the webhook route (long random path, `Authorization` secret check returning a fast 401, signature verification, size limit). Status and admin pages go on a separate tailnet-only port.
- **Alerts:** a Slack incoming webhook posts to a dedicated channel on every successful sync and on failures (state changes plus a daily reminder; token-expiry messages name the re-login command).
- **Liveness:** a healthchecks.io ping after every poll cycle (even with no new readings), and `/fail` on errors. This watches the service, not the weigh-ins.
- **Google Health data shape:** a weigh-in's weight and body-fat points share the same data-point ID and `sampleTime`. Weight is `weight.weightGrams`; body fat is `bodyFat.percentage`. The time is `sampleTime.physicalTime` (UTC) plus `utcOffset` (e.g. `"46800s"`).

## Open questions / to verify first
- [ ] Can an unverified OAuth app with Google Health restricted scopes be set to **In production** without review? (Removes the 7-day expiry.) Google's docs say the 100-user cap applies "for both testing and production", which implies yes. Not confirmed in practice yet: `aria-sync google-auth` prints `refresh_token_expires_in` from the token response (604799 = 7 days means Testing rules still apply). Setup steps are in `docs/google-oauth-setup.md`; it uses a **Desktop app** OAuth client with a localhost callback.
- [x] Do Google Health webhooks support `weight` / `body-fat`? **Yes** (confirmed 5 Nov 2026).
- [ ] How quickly does the webhook actually fire after an Aria weigh-in? (Measure it.)
- [ ] For Option A: can an n8n Webhook node handle the two-step verification (200 with the secret, 401 without)? Probably needs an IF node on the `Authorization` header.
- [ ] The exact Google Health response shape for weight/body-fat (units, IDs, timestamps, timezone) and the filter syntax.
- [ ] Which Garmin library/method gives the cleanest body composition upload (plain weigh-in vs FIT weight-scale file). Test on one reading and check it in Garmin Connect.
- [ ] Do I want a one-off **backfill** of history since SmartScaleSync stopped (late Oct / 2 Nov 2026)?
- [ ] Do I already run n8n on Unraid? (Decides A vs B.)
- [ ] Alert channel: Unraid notifications, ntfy, Pushover, email?

## Suggested build order
1. Set up the Google Cloud project and OAuth, publish to production, and run a one-off script to read the last 30 days of weight + body fat.
2. Do the first Garmin login interactively and save the tokens; upload one test reading and check it in Garmin Connect.
3. Join the two: dedup store, body-fat pairing, poll loop, error alerts.
4. Package it as a container (and an n8n workflow if Option A); deploy on Unraid with persistent volumes.
5. Optional: backfill, then webhooks.

## Sources
- Google Health API, about and turn-down timeline: https://developers.google.com/health/about
- Google Health API, setup / OAuth / token behaviour: https://developers.google.com/health/setup
- Google Health API, release notes (data types): https://developers.google.cn/health/release-notes?hl=en
- Google Health API, migration guide (scope mappings): https://developers.google.com/health/migration
- Google Health API, webhook subscriptions: https://developers.google.com/health/api/webhooks
- Garmin Personal API (the5krunner): https://the5krunner.com/2026/10/22/garmin-personal-api/
- Garmin developer program revamp (DC Rainmaker): https://www.dcrainmaker.com/2026/10/garmin-connect-api-revamps-connect-developer.html
- python-garminconnect: https://github.com/cyberjunky/python-garminconnect
- garmin-connect-api: https://pypi.org/project/garmin-connect-api/
- garmin-auth: https://pypi.org/project/garmin-auth/
- fitbitApp (Google Health API wrapper): https://pypi.org/project/fitbitApp/
