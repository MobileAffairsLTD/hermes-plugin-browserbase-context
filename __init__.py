"""User browser-provider plugin entry point — see provider.py for the why."""

from __future__ import annotations

from plugins.browser.browserbase_context.provider import BrowserbaseContextProvider


def register(ctx) -> None:
    ctx.register_browser_provider(BrowserbaseContextProvider())
