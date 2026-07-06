"""Quick auth + permissions check for the Teams connector.

Run this immediately after IT provides the Azure app Client ID to verify
every step works before starting the full agent.

Usage:
    TEAMS_TENANT_ID=f78a768a-22ae-4432-9eb4-55ce4b73c8c3 \\
    TEAMS_CLIENT_ID=<client_id_from_IT> \\
    TEAMS_USERNAME=qnoe-agent@ICFO.onmicrosoft.com \\
    TEAMS_PASSWORD=<password> \\
    python -m agent.teams_check

Each step prints PASS or FAIL with a clear reason so you know exactly
what is working and what still needs IT action.
"""
import asyncio
import base64
import json
import os
import sys

import aiohttp
import msal

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = [
    "https://graph.microsoft.com/Chat.Read",
    "https://graph.microsoft.com/Chat.ReadWrite",
    "https://graph.microsoft.com/ChatMessage.Send",
]


def _env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        print(f"  ✗ Missing env var: {key}")
        sys.exit(1)
    return val


async def main() -> None:
    print("\n=== QNOE Agent — Teams connectivity check ===\n")

    tenant_id = _env("TEAMS_TENANT_ID")
    client_id = _env("TEAMS_CLIENT_ID")
    username  = _env("TEAMS_USERNAME")
    password  = _env("TEAMS_PASSWORD")

    # ── Step 1: MSAL token acquisition ────────────────────────────────────────
    print("Step 1 — Token acquisition (MSAL ROPC) ...")
    app = msal.PublicClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )
    result = app.acquire_token_by_username_password(
        username=username, password=password, scopes=SCOPES
    )
    if "access_token" not in result:
        err = result.get("error_description") or result.get("error", "unknown")
        print(f"  FAIL — {err}")
        print("\n  Common causes:")
        print("  - Wrong client ID or tenant ID")
        print("  - 'Allow public client flows' not enabled on the app registration")
        print("  - MFA is enforced on the account (ask IT to exempt qnoe-agent)")
        print("  - Admin consent not yet granted for the required permissions")
        sys.exit(1)
    token = result["access_token"]
    print(f"  PASS — token acquired (expires in {result.get('expires_in')}s)")

    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # ── Step 2: /me — basic identity ──────────────────────────────────────
        print("\nStep 2 — GET /me (User.Read) ...")
        async with session.get(f"{GRAPH_BASE}/me", headers=headers) as resp:
            if resp.status != 200:
                body = await resp.text()
                print(f"  FAIL — HTTP {resp.status}: {body[:200]}")
                sys.exit(1)
            me = await resp.json()
        print(f"  PASS — logged in as: {me.get('displayName')} ({me.get('userPrincipalName')})")
        print(f"         user id: {me.get('id')}")

        # ── Step 3: /me/chats — Chat.Read ─────────────────────────────────────
        print("\nStep 3 — GET /me/chats (Chat.Read) ...")
        async with session.get(
            f"{GRAPH_BASE}/me/chats?$top=5&$select=id,chatType",
            headers=headers,
        ) as resp:
            if resp.status == 403:
                print("  FAIL — 403 Forbidden: Chat.Read permission not granted or no admin consent")
                sys.exit(1)
            if resp.status != 200:
                body = await resp.text()
                print(f"  FAIL — HTTP {resp.status}: {body[:200]}")
                sys.exit(1)
            chats = await resp.json()
        chat_list = chats.get("value", [])
        print(f"  PASS — found {len(chat_list)} chats (showing up to 5)")

        # ── Step 4: verify ChatMessage.Send scope in token ────────────────────
        print("\nStep 4 — Verify ChatMessage.Send scope in access token ...")
        # Decode JWT payload (no signature verification — we just want the scp claim)
        try:
            parts = token.split(".")
            padding = "=" * (4 - len(parts[1]) % 4)
            payload = json.loads(base64.b64decode(parts[1] + padding))
            granted_scopes = set(payload.get("scp", "").split())
        except Exception as exc:
            print(f"  FAIL — Could not decode token: {exc}")
            sys.exit(1)

        required = {"Chat.Read", "Chat.ReadWrite", "ChatMessage.Send"}
        missing = required - granted_scopes
        if missing:
            print(f"  FAIL — Missing scopes in token: {missing}")
            print("  Ask IT to grant admin consent for these delegated permissions.")
            sys.exit(1)
        print(f"  PASS — all required scopes present: {required}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n=== All checks passed — Teams connector is ready ===")
    print("\nNext step: set env vars and start the agent:")
    print(f"  TEAMS_TENANT_ID={tenant_id}")
    print(f"  TEAMS_CLIENT_ID={client_id}")
    print(f"  TEAMS_USERNAME={username}")
    print("  TEAMS_PASSWORD=<password>")
    print("  Then: python -m agent.main\n")


if __name__ == "__main__":
    asyncio.run(main())
