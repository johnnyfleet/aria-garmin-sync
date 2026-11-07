# Automatic updates

```
Dependabot PR (weekly, or immediately for security) ──> CI: unit tests + Docker smoke test
        │ pass & not a major bump                          │ fail, or major bump
        ▼                                                   ▼
  CI squash-merges the PR, dispatches CI on main      PR stays open for review
        ▼
  CI on main: tests + smoke again → publish ghcr.io/johnnyfleet/aria-garmin-sync:latest
        ▼
  Unraid pulls :latest (CA Auto Update Applications, or Docker → Check for Updates)
```

## What Dependabot watches

| Ecosystem | What | Auto-merged |
|---|---|---|
| `uv` | Python dependencies in `uv.lock` (grouped into one PR) | minor + patch |
| `docker` | `python:3.12-slim` and `uv` base images, pinned by digest | digest rebuilds (incl. Debian security patches) and patch tags. **Not** Python 3.12 → 3.13. |
| `github-actions` | Workflow actions (grouped) | minor + patch |

Major version bumps are ignored for routine updates. A **security** update that needs a major bump still
gets a PR, but CI leaves it open for review.

Python minor bumps are excluded because the Nix devshell (`python312` in `flake.nix`) should move at the same
time. Do those by hand.

## What "passing" means

- `pytest`: pairing weight with body fat, webhook auth/signature/handshake, signature parsing against Google's
  published keyset, alert de-duplication, and a **contract test** on the unofficial Garmin library (the methods
  and parameters we call still exist, and a FIT weight file still encodes).
- `scripts/smoke-test.sh` on the built image: dependencies import (including native wheels like
  `curl_cffi`), the CLI runs, the process drops to 99:100, the webhook handshake returns 200/401/404,
  the loop survives with no tokens, and `docker stop` is clean.

The one thing CI can't check is whether Garmin's servers still accept our login and upload, because that needs
real credentials. If an update breaks it, Slack reports the failure on the next weigh-in and healthchecks.io goes red.
Roll back by pinning the template to a previous `sha-<commit>` tag.

## One-off repo settings

- Settings → **Code security** → enable **Dependabot alerts** and **Dependabot security updates**.
  Version updates come from `.github/dependabot.yml` and need no setting.
- Check: Insights → **Dependency graph** → **Dependabot** should list three ecosystems with no errors.
