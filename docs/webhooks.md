# Webhooks (near-instant sync)

With webhooks, Google notifies the container as soon as a weigh-in lands, so it syncs within a minute or so
instead of waiting for the next poll. Polling stays on as a safety net.

```
Google Health --HTTPS--> https://<host>.<tailnet>.ts.net/hook/<random>   (Tailscale Funnel, Unraid toggle)
                          → container :8080 → secret check → signature check → 204 → wake the sync loop
```

The notification only says *something changed*. The sync loop then re-reads Google with its own token,
so a forged request can at worst cause an extra poll. Everything except `POST <path>` gets a 404.
Requests without the right `Authorization` get a 401, and requests with a bad `GOOGLE-HEALTH-API-SIGNATURE`
(ECDSA P-256, checked against Google's published keyset) get a 403.

## 1. Generate a path and secret

```sh
aria-sync webhook-secret
```

Put both lines in `data/.env` on the laptop (the `create` call below needs the secret), and paste them into
the **Webhook path** and **Webhook secret** fields of the Unraid template. They must match exactly,
including the `Bearer ` prefix.

## 2. Allow Funnel in your tailnet (one-off)

In the Tailscale admin console:
- **DNS** → make sure **HTTPS Certificates** is enabled.
- **Access controls** → allow Funnel through `nodeAttrs`, e.g.
  ```json
  "nodeAttrs": [{ "target": ["autogroup:member"], "attr": ["funnel"] }]
  ```
  (The admin console usually offers to add this for you the first time Funnel is used.)

## 3. Turn on Tailscale for the container (Unraid)

Docker → `aria-garmin-sync` → Edit:
- **Use Tailscale**: on
- **Tailscale Hostname**: e.g. `aria-sync`. It ends up in public certificate logs, so pick a name you don't mind being public.
- **Tailscale Serve**: **Funnel**
- **Show advanced settings** → **Tailscale State Directory**: `/data/.tailscale_state`
- **Show advanced Tailscale settings** → **Tailscale Serve Port**: `8080`. Without it Unraid only passes
  `TAILSCALE_FUNNEL=true`, and the hook resets Funnel on every start with nothing to serve
  (`tailscale funnel status` → `No serve config`). If the field is missing, add a variable
  `TAILSCALE_SERVE_PORT=8080`.
- Make sure **WebUI** (advanced view) is `http://[IP]:[PORT:8080]/`.
- Funnel must be allowed for the node in the tailnet policy (step 2), and the Unraid Tailscale plugin's own
  Funnel setting must be on.

Apply. The first start prints a Tailscale login link in the container log; open it to add the node.
Also: **Machines** → `aria-sync` → **Disable key expiry**, or the node drops off after 180 days.

To check it's working, run this on Unraid and then on the laptop:

```sh
docker exec aria-garmin-sync tailscale funnel status          # Funnel on → proxy http://127.0.0.1:8080
aria-sync webhook-test --base https://aria-sync.<tailnet>.ts.net
```

The test replays Google's two verification requests and should PASS both. A quick manual fix is
`docker exec aria-garmin-sync tailscale funnel --bg 8080`, but it only lasts until the container restarts.

## 4. Create the subscriber (from the laptop)

```sh
aria-sync webhook-subscriber create --project-number 138252193496 \
    --url https://aria-sync.<tailnet>.ts.net/hook/<random>
```

Google runs its two-step verification against the endpoint (with the secret → 200, without → 401).
If that fails you'll get `FAILED_PRECONDITION`; check the container log for `Answered webhook verification`.

`aria-sync webhook-subscriber list|delete --project-number 138252193496` manages it afterwards.
If you change the secret, delete and re-create the subscriber.

## 5. Test

Weigh in, then watch `docker logs -f aria-garmin-sync` for `Webhook: UPSERT weight` → `Woken by webhook`
→ `Uploaded`. The Slack message shows the delay since the weigh-in.

Polling runs hourly by default (`3600`) as a safety net for missed webhooks. Keep the healthchecks.io check's
**period at 1 hour** (with about 1 hour of grace). If you lower **Poll interval** while testing, lower the period to match.
