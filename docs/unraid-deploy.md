# Deploying on Unraid

The image is built by GitHub Actions on every push to `main` and published to
`ghcr.io/johnnyfleet/aria-garmin-sync:latest`. It runs as `99:100` (nobody:users) with all state in `/data`.

## 1. Make the image pullable

After the first workflow run, the package appears under GitHub → your profile → Packages.
Either make the package **public** (it contains no secrets), or log Unraid in to GHCR once with a
classic PAT that has `read:packages`:

```sh
docker login ghcr.io -u johnnyfleet
```

## 2. Copy the tokens and config to appdata

The Google and Garmin tokens from the laptop are portable, so there's no need to log in again on Unraid:

```sh
ssh root@unraid mkdir -p /mnt/user/appdata/aria-garmin-sync
scp data/{google_client_secret.json,google_token.json,google_token_meta.json,garmin_tokens.json,state.db} \
    root@unraid:/mnt/user/appdata/aria-garmin-sync/
ssh root@unraid 'cd /mnt/user/appdata/aria-garmin-sync && chown -R 99:100 . && chmod 700 . && chmod 600 *'
```

**Stop any local `aria-sync run` afterwards.** Two instances would both refresh the same tokens.
(Google is fine with this; Garmin may rotate its refresh token and leave one copy stale.)

## 3. Add the container

```sh
scp unraid/aria-garmin-sync.xml root@unraid:/boot/config/plugins/dockerMan/templates-user/my-aria-garmin-sync.xml
```

Then go to Docker → Add Container → Template → `aria-garmin-sync`, paste the Slack webhook and healthchecks.io URLs from `data/.env` into their (masked) fields, and Apply.

Check that it's working:

- `docker logs aria-garmin-sync` shows `Polling every 300s`.
- After about 5 minutes, the healthchecks.io check is green and the Docker tab shows the container as **healthy**.
- On your next weigh-in, Slack posts ✅ within about 5 minutes.

## Re-authenticating later

Slack tells you which command to run when a token stops working.

**Garmin** (password + email MFA), from the Unraid terminal:

```sh
docker exec -it aria-garmin-sync aria-sync garmin-login
```

**Google**: the consent callback listens on `localhost:8080` inside the container, which is awkward to
reach. The easiest way is to re-run consent on the laptop (`aria-sync google-auth`) and copy
`google_token.json` and `google_token_meta.json` to appdata as in step 2 (chown `99:100`), then restart the container.

## Useful commands

```sh
docker exec aria-garmin-sync aria-sync sync-once
docker exec aria-garmin-sync aria-sync backfill --since 2026-11-01 --dry-run
docker exec aria-garmin-sync aria-sync test-alerts
```
