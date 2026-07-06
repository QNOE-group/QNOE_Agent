# SharePoint Access for QNOE Agent — Setup Manual

This guide explains how to give the QNOE lab agent read access to SharePoint sites.

---

## Overview

The agent uses Microsoft Graph API to read SharePoint files. Two things are needed:

1. **Azure AD app permissions** (one-time, done by ICFO IT)
2. **Per-site membership** (done by each SharePoint site admin)

---

## Step 1 — Azure AD App Permissions (ICFO IT)

The QNOE-AI app registration needs SharePoint-related Graph API scopes.

**Who:** ICFO IT admin with Azure AD (Entra ID) access.

**What to do:**

1. Open [Azure Portal](https://portal.azure.com)
2. Go to **App registrations** → find **"QNOE-AI"** (App ID: `108a03c5-e265-4ab6-a5ea-9c902fd527d4`)
3. Go to **API permissions** → click **Add a permission**
4. Select **Microsoft Graph** → **Delegated permissions**
5. Search and add these two permissions:
   - `Sites.Read.All` — Read items in all site collections
   - `Files.Read.All` — Read all files that user can access
6. Click **Grant admin consent for ICFO**

**Status:** Not yet done. Current app only has Chat/Message permissions for Teams.

---

## Step 2 — Add the Agent to Each SharePoint Site

Each SharePoint site that the agent should read needs to grant access to the agent's user account.

**Agent account:** `qnoe-agent@ICFO.onmicrosoft.com`

**Who:** The SharePoint site owner/admin.

**What to do:**

1. Open the SharePoint site in a browser
2. Click the **gear icon** (top right) → **Site permissions**
3. Click **Add members** (or **Share site**)
4. Type `qnoe-agent@ICFO.onmicrosoft.com`
5. Select the **Reader** (or **Visitor**) role — the agent only needs read access
6. Click **Share** / **Save**

---

## How to Find a SharePoint Site Admin

If you don't know who owns a SharePoint site:

- **Option A:** On the site → gear icon → **Site permissions** → look for the **Owners** group
- **Option B:** On the site → click **Members** (left sidebar or top bar) → look for **Owners**
- **Option C:** Ask ICFO IT to look it up in the **SharePoint admin center** → Sites → select the site → Membership tab

---

## Verification

After both steps are complete, run this test on the DGX:

```bash
/opt/qnoe-agent/hermes-venv/bin/python3 -c "
import msal, requests

app = msal.PublicClientApplication(
    '108a03c5-e265-4ab6-a5ea-9c902fd527d4',
    authority='https://login.microsoftonline.com/f78a768a-22ae-4432-9eb4-55ce4b73c8c3'
)

result = app.acquire_token_by_username_password(
    username='qnoe-agent@ICFO.onmicrosoft.com',
    password='<password>',
    scopes=['Sites.Read.All', 'Files.Read.All']
)

if 'access_token' in result:
    # List accessible SharePoint sites
    headers = {'Authorization': f'Bearer {result[\"access_token\"]}'}
    resp = requests.get('https://graph.microsoft.com/v1.0/sites?search=*', headers=headers)
    sites = resp.json().get('value', [])
    for s in sites:
        print(f'{s[\"displayName\"]:40s} {s[\"webUrl\"]}')
else:
    print(f'Auth failed: {result.get(\"error_description\", \"\")[:200]}')
"
```

If it prints a list of SharePoint sites, access is working.

---

## What Happens Next (Agent-Side)

Once access is granted, the agent-side work is:

1. **Ingestion:** Extend the ingestion pipeline to crawl SharePoint document libraries via Graph API, download files, and index them into Qdrant collections
2. **Incremental updates:** Use Graph API delta queries or the existing watcher pattern to detect new/changed files
3. **Agent tool:** The agent can use its existing `read_file` tool for local files; SharePoint files will be available through RAG after ingestion
