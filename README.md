# aria-garmin-sync

Syncs weigh-ins (weight and body fat %) from a **Fitbit Aria** scale to **Garmin Connect**, self-hosted as a small Docker container on Unraid.

## Why

I have Aria scales and want my weigh-ins to keep showing up in Garmin Connect. I used to do this with SmartScaleSync, but:

- Google turned off the legacy **Fitbit Web API** on 2 Nov 2026. Its requests now return `410 Gone`. The replacement is the **Google Health API**.
- SmartScaleSync doesn't support the Google Health API yet, so it stopped syncing.

This project fills the gap for my own account until that changes.

## How it works

```
Aria --wifi--> Fitbit / Google Health --(webhook via Tailscale Funnel, + polling)--> aria-sync --> Garmin Connect
```

1. Reads new `weight` and `body-fat` data points from the Google Health API, using Google OAuth with a long-lived refresh token.
2. Matches each weight with its body-fat reading. Both share a data-point ID.
3. Uploads the weigh-in to Garmin Connect as a FIT weight-scale file, the same format Garmin's Index scales use, via the unofficial [python-garminconnect](https://github.com/cyberjunky/python-garminconnect) library. Garmin's official Personal API is read-only.
4. Records what it has uploaded in SQLite, and also checks Garmin for an existing weigh-in at the same time, so readings never get duplicated.
5. Posts each sync and any failures to Slack, and pings healthchecks.io after every cycle.

## Setup

- [Google OAuth setup](docs/google-oauth-setup.md): Cloud project, consent screen (published, so tokens don't expire after 7 days), OAuth client, first consent.
- `aria-sync garmin-login`: one-off interactive Garmin login, including email MFA. Later runs use the saved tokens only.
- [Deploying on Unraid](docs/unraid-deploy.md): GHCR image, Unraid template, copying tokens over.
- [Webhooks](docs/webhooks.md): near-instant sync through Tailscale Funnel (Unraid's per-container Tailscale toggle).

Local development uses a Nix flake devshell (`direnv allow`), and Python dependencies are managed with uv.

## Commands

| Command | What it does |
|---|---|
| `aria-sync run` | Poll forever (the container's default) |
| `aria-sync sync-once` | Run one sync cycle |
| `aria-sync backfill --since YYYY-MM-DD [--dry-run]` | Upload any readings Garmin is missing |
| `aria-sync push-latest [--dry-run]` | Upload the most recent reading |
| `aria-sync google-auth` / `google-status` / `google-fetch` | Google consent, token check, raw data dump |
| `aria-sync garmin-login` / `garmin-check` | Garmin login, token check and recent weigh-ins |
| `aria-sync webhook-secret` / `webhook-subscriber create\|list\|delete` | Webhook path/secret, Google subscriber management |
| `aria-sync test-alerts` | Send a test Slack message and healthcheck ping |

## Caveats

- This is a personal tool for a single user. The Google OAuth app is unverified, so you'll see a "Google hasn't verified this app" warning when you give consent.
- The Garmin side uses an unofficial login flow and could break if Garmin changes it. If it does, Slack will say so.
- Tokens in `data/` are secrets. They're git-ignored and written with `0600` permissions.
