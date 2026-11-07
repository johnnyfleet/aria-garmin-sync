# Google Health API OAuth setup

Do all of this signed in as your **personal Google account** (the one that holds the Fitbit data).
The Cloud project lives under that account and the same account gives consent.

## 0. Prerequisite: link Fitbit to Google Health

The Google Health API returns nothing until the account is linked in the **Google Health** (Fitbit) mobile app.
Open the app, make sure it's signed in with your personal Google account, and that recent Aria weigh-ins appear.

## 1. Create the project and enable the API (CLI)

From the project directory (the devshell provides `gcloud`):

```sh
gcloud auth login                       # browser login as the personal account
gcloud projects create aria-garmin-sync-<suffix> --name="Aria Garmin Sync"
gcloud config set project aria-garmin-sync-<suffix>
gcloud services enable health.googleapis.com
gcloud projects describe aria-garmin-sync-<suffix> --format='value(projectNumber)'   # keep for webhooks later
```

Project IDs are globally unique, so pick any suffix. No billing account is needed.

## 2. Google Auth Platform (console)

Open https://console.cloud.google.com/auth/overview?project=aria-garmin-sync-<suffix> and click **Get started**:

1. **App information**: app name `Aria Garmin Sync`, support email = your personal address.
2. **Audience**: **External**.
3. **Contact information**: your personal address.
4. Accept the policy and click **Create**.

Then:

- **Data Access** → *Add or remove scopes* → search "Google Health API" → tick
  `.../auth/googlehealth.health_metrics_and_measurements.readonly` → *Update* → *Save*.
- **Audience** → under *Publishing status* click **Publish app** → confirm.
  The status should read **In production**. Google may show a notice that verification is needed;
  for a single-user personal app you can ignore it (unverified apps are capped at 100 users,
  and users see a "Google hasn't verified this app" warning).
  You don't need test users once the app is published.

## 3. Create the OAuth client (console)

**Clients** → *Create client*:

- Application type: **Desktop app** (it allows any `http://localhost:<port>` redirect, so you don't have to register a redirect URI).
- Name: `aria-sync-cli`.
- Click **Create**, then **Download JSON** and save it as `data/google_client_secret.json`:

```sh
mv ~/Downloads/client_secret_*.json data/google_client_secret.json
chmod 600 data/google_client_secret.json
```

## 4. Give consent and check the token

```sh
aria-sync google-auth          # opens a browser; on a headless box add --no-browser
```

On the consent screen:
1. Choose the personal account.
2. "Google hasn't verified this app" → **Advanced** → **Go to Aria Garmin Sync (unsafe)**.
3. Tick the health-metrics permission → **Continue**.

The command shows whether Google set a refresh-token lifetime:

- `no refresh-token expiry set by Google (app is In production)`: production publishing worked.
- `refresh token expires in 7.0 days`: the app is still in Testing (or Google is enforcing
  Testing rules for unverified restricted scopes). Check the publishing status, then re-run `google-auth`.

Then:

```sh
aria-sync google-status        # refreshes the access token and calls /users/me/identity
aria-sync google-fetch --days 30 > data/sample.json
```

### Doing the consent from the Unraid box later

`google-auth` listens on `localhost:8080`. From a laptop:

```sh
ssh -L 8080:localhost:8080 unraid    # then run `aria-sync google-auth --no-browser` in the container
```

Open the printed URL in the laptop's browser; the redirect reaches the container through the tunnel.
Or run consent on the laptop and copy `data/google_token.json` across (it's portable).

## Secrets

`data/` is git-ignored. `google_client_secret.json` and `google_token.json` are both secrets.
The token file is written with `0600` permissions.
