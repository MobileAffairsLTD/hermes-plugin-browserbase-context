# hermes-plugin-browserbase-context

A Hermes **browser provider plugin**: Browserbase sessions bound to a persistent **Context**, so a one-time human login (LinkedIn, a partner portal, anything with a session) is reused by every later agent run instead of starting logged out.

## Why it exists

Hermes ships a bundled `browserbase` provider (`plugins/browser/browserbase/provider.py`). It creates a **fresh session per run** and never sends `browserSettings.context` — correct for scraping, wrong for "log in once, keep using it". This plugin subclasses it and injects the context id, nothing else changes.

## Install

```bash
hermes plugins install MobileAffairsLTD/hermes-plugin-browserbase-context
hermes plugins enable browser/browserbase-context
hermes config set --force browser.cloud_provider browserbase-context
```

For a non-default profile (`hermes -p <profile> ...`), the plugin directory must be visible from that profile's home — symlink it:

```bash
mkdir -p ~/.hermes/profiles/<profile>/plugins/browser
ln -sfn ~/.hermes/plugins/browser/browserbase-context \
        ~/.hermes/profiles/<profile>/plugins/browser/browserbase-context
hermes -p <profile> plugins enable browser/browserbase-context
```

## Environment

| Var | Purpose |
|---|---|
| `BROWSERBASE_API_KEY` | required |
| `BROWSERBASE_PROJECT_ID` | required |
| `BROWSERBASE_CONTEXT_ID` | **required** — the context holding the logged-in state |
| `BROWSERBASE_PROXIES` | default `true` (residential) |
| `BROWSERBASE_KEEP_ALIVE` | default `true` |
| `BROWSERBASE_CONTEXT_PERSIST` | default `true` — write cookies back to the context |
| `BROWSERBASE_ADVANCED_STEALTH` | default `false`; **403 on the Developer plan** — leave off |
| `BROWSERBASE_SESSION_TIMEOUT` | seconds, max 21600 |

## Operate

```bash
# create a context once per site identity
curl -s -X POST https://api.browserbase.com/v1/contexts \
  -H "X-BB-API-Key: $BROWSERBASE_API_KEY" -H 'Content-Type: application/json' \
  -d '{"projectId":"'"$BROWSERBASE_PROJECT_ID"'"}'

# log in once: create a context-bound session, then open it in the dashboard
#   https://www.browserbase.com/sessions/<session_id>
# then release it — the cookies are persisted into the context
```

Verified 2026-09-17 against a live project: session created with `contextId` echoed back by the API, proxies and keep-alive active, clean release.

## Known limits (Browserbase Developer plan, measured)

- **Concurrent sessions are a *project* setting**, not a plan entitlement: a fresh project defaults to `concurrency: 1` even though the plan allows 25. Raise it in the dashboard (Project Settings). The API has **no** route to change it (`PATCH/PUT/POST /v1/projects/{id}` → 404).
- **Advanced stealth → 403** on Developer; the provider drops it and warns rather than failing the run.
- One held-open session (e.g. waiting for a human login) **blocks every other agent run** in a `concurrency: 1` project.
