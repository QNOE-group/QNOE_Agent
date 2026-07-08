"""Microsoft Teams connector via Graph API (polling, no webhooks).

Authentication: MSAL ROPC (username + password) using the qnoe-agent service
account. Credentials injected via environment variables (never on disk).

Required env vars:
  TEAMS_TENANT_ID   — f78a768a-22ae-4432-9eb4-55ce4b73c8c3
  TEAMS_CLIENT_ID   — Azure app registration client ID (from IT)
  TEAMS_USERNAME    — qnoe-agent@ICFO.onmicrosoft.com
  TEAMS_PASSWORD    — service account password

Optional env vars:
  TEAMS_CHANNEL_IDS — JSON dict mapping sub-agent name to "teamId/channelId"
                      e.g. {"qtm": "abc.../xyz...", "photocurrent": "..."}

Polling strategy:
  Active (message received in last 5 min):  3 s
  Idle:                                     30 s

Design notes:
  - Own user ID is fetched on startup and used to filter out self-replies.
  - Historical messages (before startup) are ignored via startup timestamp.
  - Seen message IDs (capped at 5000) prevent double-processing within a session.
  - Chat list is re-enumerated every 5 minutes to pick up new conversations.
  - 429 Rate-limit responses are honoured via Retry-After header.
"""
import asyncio
import json
import logging
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Awaitable, Callable

import aiohttp
import msal

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = [
    "https://graph.microsoft.com/Chat.Read",
    "https://graph.microsoft.com/Chat.ReadWrite",
    "https://graph.microsoft.com/ChatMessage.Send",
]
ACTIVE_POLL_INTERVAL = 3      # seconds when recently active
IDLE_POLL_INTERVAL = 10       # seconds when idle
ACTIVE_WINDOW = 300           # seconds before switching to idle
CHAT_REFRESH_INTERVAL = 300   # seconds between chat list refreshes
MAX_SEEN_IDS = 5000           # cap on in-memory dedup set


class TeamsConnector:
    def __init__(self) -> None:
        self.tenant_id = os.environ["TEAMS_TENANT_ID"]
        self.client_id = os.environ["TEAMS_CLIENT_ID"]
        self.username = os.environ["TEAMS_USERNAME"]
        self.password = os.environ["TEAMS_PASSWORD"]
        self.channel_ids: dict[str, str] = json.loads(
            os.environ.get("TEAMS_CHANNEL_IDS", "{}")
        )

        self._app = msal.PublicClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
        )
        self._token: str | None = None
        self._token_expires: float = 0.0

        # Set on first _bootstrap() call
        self._me_id: str = ""
        self._startup_ts: datetime = datetime.min.replace(tzinfo=timezone.utc)

        # Known DM chat IDs and when to next refresh the list
        self._chat_ids: set[str] = set()
        self._chat_refresh_at: float = 0.0

        # Dedup: fixed-size queue of recently seen message IDs
        self._seen_msg_ids: deque[str] = deque(maxlen=MAX_SEEN_IDS)
        self._seen_set: set[str] = set()

        self._last_message_time: float = 0.0
        self._session: aiohttp.ClientSession | None = None

        # Callback: async (conversation_id, thread_id, user_id, text) -> str
        self.on_message: Callable[[str, str | None, str, str], Awaitable[str]] | None = None

    # ── Authentication ─────────────────────────────────────────────────────────

    async def _get_token(self) -> str:
        """Return a valid access token, refreshing if within 60 s of expiry."""
        if self._token and time.time() < self._token_expires - 60:
            return self._token

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self._acquire_token_sync)

        if "access_token" not in result:
            error = result.get("error_description") or result.get("error", "unknown")
            raise RuntimeError(f"MSAL token acquisition failed: {error}")

        self._token = result["access_token"]
        self._token_expires = time.time() + result.get("expires_in", 3600)
        return self._token

    def _acquire_token_sync(self) -> dict:
        """Synchronous MSAL token acquisition (runs in executor)."""
        # Try silent refresh first (uses cached refresh token from previous call)
        accounts = self._app.get_accounts(username=self.username)
        if accounts:
            result = self._app.acquire_token_silent(SCOPES, account=accounts[0])
            if result and "access_token" in result:
                return result
        # Fall back to full ROPC
        return self._app.acquire_token_by_username_password(
            username=self.username,
            password=self.password,
            scopes=SCOPES,
        )

    async def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {await self._get_token()}",
            "Content-Type": "application/json",
        }

    # ── HTTP helpers ───────────────────────────────────────────────────────────

    async def _get(self, url: str) -> dict:
        assert self._session is not None
        for attempt in range(3):
            async with self._session.get(url, headers=await self._headers()) as resp:
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", "10"))
                    logger.warning("Rate limited — sleeping %ds", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                return await resp.json()
        raise RuntimeError(f"GET {url} failed after retries")

    async def _post(self, url: str, body: dict) -> dict:
        assert self._session is not None
        for attempt in range(3):
            async with self._session.post(
                url, json=body, headers=await self._headers()
            ) as resp:
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", "10"))
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                return await resp.json()
        raise RuntimeError(f"POST {url} failed after retries")

    # ── Bootstrap ──────────────────────────────────────────────────────────────

    async def _bootstrap(self) -> None:
        """Fetch own user ID and enumerate existing chats (marking them as seen)."""
        me = await self._get(f"{GRAPH_BASE}/me?$select=id,displayName")
        self._me_id = me["id"]
        self._startup_ts = datetime.now(timezone.utc)
        logger.info("Authenticated as %s (id=%s)", me.get("displayName"), self._me_id)
        logger.info("Ignoring messages before %s", self._startup_ts.isoformat())
        await self._refresh_chat_list()

    async def _refresh_chat_list(self) -> None:
        """Re-enumerate DM chats. Called on startup and every CHAT_REFRESH_INTERVAL."""
        try:
            data = await self._get(
                f"{GRAPH_BASE}/me/chats?$select=id,chatType&$top=50"
            )
            self._chat_ids = {
                c["id"] for c in data.get("value", [])
                if c.get("chatType") == "oneOnOne"
            }
            self._chat_refresh_at = time.time() + CHAT_REFRESH_INTERVAL
            logger.debug("Tracking %d DM chats", len(self._chat_ids))
        except Exception as exc:
            logger.warning("Chat list refresh failed: %s", exc)

    # ── Deduplication ──────────────────────────────────────────────────────────

    def _is_new(self, msg_id: str) -> bool:
        """Return True if this message ID has not been seen before."""
        if msg_id in self._seen_set:
            return False
        # Evict oldest if at capacity
        if len(self._seen_msg_ids) == MAX_SEEN_IDS:
            evicted = self._seen_msg_ids[0]
            self._seen_set.discard(evicted)
        self._seen_msg_ids.append(msg_id)
        self._seen_set.add(msg_id)
        return True

    def _after_startup(self, iso_str: str) -> bool:
        """Return True if the ISO timestamp is after agent startup."""
        try:
            ts = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return ts > self._startup_ts
        except (ValueError, TypeError):
            return False

    # ── Polling ────────────────────────────────────────────────────────────────

    async def _poll_chat_messages(self, chat_id: str) -> list[dict]:
        """Return new, non-self messages in a DM chat since startup."""
        try:
            data = await self._get(
                f"{GRAPH_BASE}/chats/{chat_id}/messages"
                f"?$top=10&$orderby=createdDateTime desc"
            )
        except Exception as exc:
            logger.warning("Message fetch error for chat %s: %s", chat_id, exc)
            return []

        results = []
        for msg in data.get("value", []):
            if msg.get("messageType") != "message":
                continue
            msg_id = msg.get("id", "")
            if not self._is_new(msg_id):
                continue
            # Ignore messages predating startup
            if not self._after_startup(msg.get("createdDateTime", "")):
                continue
            # Ignore own messages (prevents reply loop)
            sender_id = ((msg.get("from") or {}).get("user") or {}).get("id", "")
            if sender_id == self._me_id:
                continue
            results.append(msg)
        return results

    async def _poll_channel(self, team_agent: str) -> list[dict]:
        """Return new channel messages for a sub-team channel."""
        channel_id_str = self.channel_ids.get(team_agent)
        if not channel_id_str or "/" not in channel_id_str:
            return []
        team_id, ch_id = channel_id_str.split("/", 1)
        try:
            data = await self._get(
                f"{GRAPH_BASE}/teams/{team_id}/channels/{ch_id}/messages"
                f"?$top=10&$orderby=createdDateTime desc"
            )
        except Exception as exc:
            logger.warning("Channel poll error for %s: %s", team_agent, exc)
            return []

        results = []
        for msg in data.get("value", []):
            if msg.get("messageType") != "message":
                continue
            msg_id = msg.get("id", "")
            if not self._is_new(msg_id):
                continue
            if not self._after_startup(msg.get("createdDateTime", "")):
                continue
            sender_id = ((msg.get("from") or {}).get("user") or {}).get("id", "")
            if sender_id == self._me_id:
                continue
            results.append(msg)
        return results

    # ── Sending ────────────────────────────────────────────────────────────────

    async def send_dm(self, chat_id: str, text: str) -> None:
        await self._post(
            f"{GRAPH_BASE}/chats/{chat_id}/messages",
            {"body": {"content": text, "contentType": "text"}},
        )

    async def send_channel_reply(
        self, team_id: str, channel_id: str, message_id: str, text: str
    ) -> None:
        await self._post(
            f"{GRAPH_BASE}/teams/{team_id}/channels/{channel_id}"
            f"/messages/{message_id}/replies",
            {"body": {"content": text, "contentType": "text"}},
        )

    # ── Main loop ──────────────────────────────────────────────────────────────

    async def _poll_cycle(self) -> None:
        if self.on_message is None:
            return

        # Refresh chat list periodically
        if time.time() >= self._chat_refresh_at:
            await self._refresh_chat_list()

        # DM chats
        for chat_id in list(self._chat_ids):
            for msg in await self._poll_chat_messages(chat_id):
                user_id = ((msg.get("from") or {}).get("user") or {}).get("id", "unknown")
                text = (msg.get("body") or {}).get("content", "").strip()
                if not text:
                    continue
                self._last_message_time = time.time()
                try:
                    reply = await self.on_message(chat_id, None, user_id, text)
                    if reply:
                        await self.send_dm(chat_id, reply)
                except Exception as exc:
                    logger.error("on_message error for chat %s: %s", chat_id, exc)

        # Sub-team channels
        for team_agent in self.channel_ids:
            for msg in await self._poll_channel(team_agent):
                user_id = ((msg.get("from") or {}).get("user") or {}).get("id", "unknown")
                text = (msg.get("body") or {}).get("content", "").strip()
                if not text:
                    continue
                channel_id_str = self.channel_ids[team_agent]
                team_id, ch_id = channel_id_str.split("/", 1)
                msg_id = msg.get("id", "")
                thread_id = msg.get("replyToId") or msg_id
                self._last_message_time = time.time()
                try:
                    reply = await self.on_message(
                        f"channel_{team_agent}", thread_id, user_id, text
                    )
                    if reply:
                        await self.send_channel_reply(team_id, ch_id, msg_id, reply)
                except Exception as exc:
                    logger.error("on_message error for channel %s: %s", team_agent, exc)

    async def run(self) -> None:
        """Bootstrap, then continuously poll Teams and dispatch messages."""
        self._session = aiohttp.ClientSession()
        try:
            await self._bootstrap()
            logger.info("Teams connector running")
            while True:
                try:
                    await self._poll_cycle()
                except Exception as exc:
                    logger.error("Poll cycle error: %s", exc, exc_info=True)
                idle = (time.time() - self._last_message_time) > ACTIVE_WINDOW
                await asyncio.sleep(IDLE_POLL_INTERVAL if idle else ACTIVE_POLL_INTERVAL)
        finally:
            await self._session.close()
