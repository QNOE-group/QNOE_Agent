"""QNOE access-control plugin.

Sends a polite refusal to Teams users who are not on the gateway allowlist,
instead of the gateway's default silent drop.

Security model — defense in depth:
  * The gateway core is the REAL enforcement point. With
    ``GATEWAY_ALLOW_ALL_USERS=false`` and ``GATEWAY_ALLOWED_USERS`` set to the
    permitted Azure AD IDs, ``GatewayRunner._is_user_authorized`` denies every
    non-listed sender regardless of this plugin. If this hook fails to load or
    raises, unauthorized users are STILL blocked (they just get silence).
  * This hook only adds the friendly *message*. It runs on the
    ``pre_gateway_dispatch`` hook (fired before auth), reuses the gateway's own
    ``_is_user_authorized`` as the single source of truth, and for an
    unauthorized Teams DM it schedules a one-time polite refusal then returns
    ``{"action": "skip"}`` so the gateway drops the message without pairing.

Why the send is scheduled as a background task: ``invoke_hook`` calls the
callback synchronously (``ret = cb(**kwargs)``, not awaited), but
``adapter.send`` is a coroutine. We are already inside the gateway's running
event loop, so we schedule the send with ``loop.create_task`` and return
immediately.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Only this platform is gated here (the QNOE Teams polling adapter).
_PLATFORM = "teams_polling"

# Refuse at most once per user per window, so a spamming sender is not flooded
# with replies. Keyed by user_id -> last-refusal epoch seconds.
_REFUSAL_WINDOW_S = 3600
_last_refusal: dict[str, float] = {}

# Keep strong refs to in-flight send tasks so they are not garbage-collected
# before completion (asyncio only holds a weak reference).
_bg_tasks: set[asyncio.Task] = set()

REFUSAL_TEXT = (
    "Sorry — you're not authorized to use the QNOE lab agent yet. "
    "If you think you should have access, please contact Yuval Zamir to be added."
)


async def _safe_send(adapter: Any, chat_id: str, text: str) -> None:
    try:
        await adapter.send(chat_id, text)
    except Exception as exc:  # pragma: no cover - network path
        logger.warning("qnoe_authz: refusal send failed: %s", exc)


def _schedule_refusal(adapter: Any, chat_id: str) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop (e.g. unit test / bare runner) — nothing to send.
        return
    task = loop.create_task(_safe_send(adapter, chat_id, REFUSAL_TEXT))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


def _pre_gateway_dispatch(
    event: Any = None,
    gateway: Any = None,
    session_store: Any = None,
    **_: Any,
) -> Optional[dict]:
    """Refuse non-allowlisted Teams DMs with a polite message.

    Returns ``{"action": "skip"}`` to drop unauthorized Teams messages after
    sending the refusal, or ``None`` to let the gateway handle the message
    normally (authorized users, other platforms, or any error).
    """
    try:
        source = getattr(event, "source", None)
        if source is None or gateway is None:
            return None

        platform = getattr(source, "platform", None)
        if platform is None or getattr(platform, "value", "") != _PLATFORM:
            return None  # not our platform — leave untouched

        # Single source of truth: the gateway's own authorization check.
        try:
            if gateway._is_user_authorized(source):
                return None  # authorized — normal dispatch
        except Exception as exc:
            # Fail closed for the message, but let the gateway's own auth run:
            # do not skip here, so the core deny path still fires.
            logger.warning("qnoe_authz: _is_user_authorized raised: %s", exc)
            return None

        # Unauthorized Teams user. Send a one-time polite refusal (DMs only),
        # then skip so the gateway drops the message (no pairing code).
        user_id = getattr(source, "user_id", None) or ""
        chat_id = getattr(source, "chat_id", None)
        chat_type = getattr(source, "chat_type", "") or ""

        logger.warning(
            "qnoe_authz: refusing unauthorized Teams user id=%s name=%s chat=%s",
            user_id,
            getattr(source, "user_name", None),
            chat_id,
        )

        if chat_type == "dm" and chat_id:
            now = time.time()
            if now - _last_refusal.get(user_id, 0.0) >= _REFUSAL_WINDOW_S:
                _last_refusal[user_id] = now
                adapter = (getattr(gateway, "adapters", {}) or {}).get(platform)
                if adapter is not None:
                    _schedule_refusal(adapter, chat_id)

        return {"action": "skip", "reason": "unauthorized (qnoe allowlist)"}
    except Exception as exc:
        logger.warning("qnoe_authz: hook error: %s", exc)
        return None


def register(ctx) -> None:
    """Register the pre-dispatch authorization hook with Hermes Agent."""
    ctx.register_hook("pre_gateway_dispatch", _pre_gateway_dispatch)
