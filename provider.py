"""User browser-provider plugin: Browserbase sessions bound to a persistent Context.

Why it exists: the bundled `browserbase` provider creates a fresh session per run and never
passes `browserSettings.context`, so cookies/logins do not survive between agent runs. This
subclass injects the context id from the environment, which is what makes a one-time human
login reusable by every later run.

Enable:  plugins.enabled: ["browser-browserbase-context"]  +  browser.cloud_provider: browserbase-context
Env:     BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID, BROWSERBASE_CONTEXT_ID
"""

from __future__ import annotations

import os
from typing import Dict

from plugins.browser.browserbase.provider import BrowserbaseBrowserProvider, _PAID_FEATURE_FALLBACKS
from agent.secret_scope import get_secret


class BrowserbaseContextProvider(BrowserbaseBrowserProvider):
    """Browserbase, with every session bound to a persistent Context."""

    provider_id = "browserbase-context"
    label = "Browserbase (persistent context)"
    setup_tag = "Browserbase with a persistent login (context)"

    def context_id(self) -> str:
        return (get_secret("BROWSERBASE_CONTEXT_ID", "") or "").strip()

    def is_available(self) -> bool:
        return super().is_available() and bool(self.context_id())

    def create_session(self, task_id: str) -> Dict[str, object]:
        config = self._get_config()
        context = self.context_id()
        if not context:
            raise ValueError(
                "browserbase-context requires BROWSERBASE_CONTEXT_ID (the Browserbase context "
                "holding the logged-in state). Create one in the Browserbase dashboard or with "
                "POST /v1/contexts, then set the env var.")

        enable_proxies = os.environ.get("BROWSERBASE_PROXIES", "true").lower() != "false"
        enable_advanced_stealth = os.environ.get("BROWSERBASE_ADVANCED_STEALTH", "false").lower() == "true"
        enable_keep_alive = os.environ.get("BROWSERBASE_KEEP_ALIVE", "true").lower() != "false"
        custom_timeout_ms = os.environ.get("BROWSERBASE_SESSION_TIMEOUT")
        persist = os.environ.get("BROWSERBASE_CONTEXT_PERSIST", "true").lower() != "false"

        session_config: Dict[str, object] = {
            "projectId": config["project_id"],
            # the whole point of this provider
            "browserSettings": {"context": {"id": context, "persist": persist}},
        }
        if enable_keep_alive:
            session_config["keepAlive"] = True
        if custom_timeout_ms:
            try:
                timeout_val = int(custom_timeout_ms)
                if timeout_val > 0:
                    session_config["timeout"] = timeout_val
            except ValueError:
                self._log.warning("Invalid BROWSERBASE_SESSION_TIMEOUT value: %s", custom_timeout_ms)
        if enable_proxies:
            session_config["proxies"] = True
        if enable_advanced_stealth:
            # advancedStealth shares the browserSettings object with context — merge, don't replace.
            session_config["browserSettings"] = {
                "context": {"id": context, "persist": persist},
                "advancedStealth": True,
            }

        url = f"{config['base_url']}/v1/sessions"
        headers = self._headers(config)
        response = self._post_create(url, headers, session_config)

        # Same 402 degradation path as the bundled provider; drop paid extras before the context.
        dropped = set()
        for key, warning in _PAID_FEATURE_FALLBACKS:
            if response.status_code == 402 and key in session_config:
                dropped.add(key)
                self._log.warning(warning)
                session_config.pop(key)
                response = self._post_create(url, headers, session_config)
        self._check_created(response)

        session_data = response.json()
        session_name = self._session_name(task_id)
        features_enabled = {
            "context": context,
            "context_persist": persist,
            "basic_stealth": True,
            "proxies": enable_proxies and "proxies" not in dropped,
            "advanced_stealth": enable_advanced_stealth,
            "keep_alive": enable_keep_alive and "keepAlive" not in dropped,
            "custom_timeout": bool(custom_timeout_ms) and "timeout" in session_config,
        }
        self._log.info("Created Browserbase session %s on context %s with features: %s",
                       session_name, context, ", ".join(k for k, v in features_enabled.items() if v and v is not False))
        return {
            "session_name": session_name,
            "bb_session_id": session_data["id"],
            "cdp_url": session_data["connectUrl"],
            "features": features_enabled,
        }
