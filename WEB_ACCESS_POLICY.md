# Web Access Policy — Decision Brief

*For: PI (Frank Koppens) · Prepared: 2026-07-15 · Status: awaiting decision (TODO line 42, [[memory/decisions#D16]] option 4)*

## The decision

Web/search tools are **deliberately off**. The founding constraint of this system is **"no data leaves the lab network,"** and web search is the one capability that punctures it. So this is a **policy exception**, not a config toggle — hence PI-level.

The real risk is **query egress**, not the results coming back. When the agent searches, *the model itself* composes the query string, which can embed confidential context (an unpublished sample code, a result, a collaborator) with no human reviewing it first. That string then leaves the network. Public results flowing back in are comparatively low-risk. So the question is: **are we willing to let the agent send self-composed queries to the internet, and under what limits?**

## How egress is controlled today (the technical hook)

The agent already runs inside the B7-OS sandbox behind an **L7 proxy that allows outbound traffic *by hostname*** (`HTTP_PROXY=10.200.0.1:3128`; allowlist lives in `network_policies` in `config/sandbox-policy.yaml`). Today only these hosts are reachable: the local LLM + Qdrant, `api.github.com`/`github.com`, and `graph.microsoft.com`/`login.microsoftonline.com` for Teams. **Everything else gets a 502.** Any web option below is implemented by (a) adding hosts to that allowlist and (b) re-enabling a Hermes `web`/fetch toolset so the model can issue the request. This chokepoint is what makes the scoped options genuinely enforceable, not just polite.

## The four options

| Option | What leaves the lab | Effort | Privacy |
|---|---|---|---|
| **1. Stay closed** (status quo) | Nothing | 0 | Full |
| **2. Allowlisted fetch** — arXiv + named journal hosts only, no open search | Requests only to whitelisted hosts | Low | Near-full |
| **3. Self-hosted metasearch** (SearXNG on the DGX) | Query *strings*, but with no lab identity attached | Medium | Partial |
| **4. Frontier-provider search** (via [[PHASE2_BACKLOG]] B4) | Query strings **and** context, to a commercial LLM vendor | High | Lowest |

### Option 2 — Allowlisted fetch (recommended default)
Add a policy block (e.g. `host: arxiv.org`, `export.arxiv.org`, a short journal list) to the proxy allowlist and give the model a `fetch_url`-style tool. It can then pull a paper by arXiv ID or open a known journal page — but it **physically cannot** broadcast an arbitrary query to Google, because any non-allowlisted host is 502'd at the proxy. This captures most of the research value (reaching published literature) while keeping the "no data leaves the lab" promise almost entirely intact. Enforcement is structural, not instruction-based.

### Option 3 — Self-hosted metasearch (SearXNG), explained
This is the option to open up **general, open-ended** search while minimising *who-is-asking* leakage. It works by inserting a middleman **you run and own**:

```
agent ──(local only)──▶ SearXNG on the DGX ──(internet)──▶ Google / Bing / DuckDuckGo…
```

**SearXNG** is an open-source, self-hostable *metasearch engine*: it takes one query, fans it out to many public engines, aggregates the results, and returns them — with no ads, no tracking cookies, and **no account**. You run it as a container on the DGX. The agent's search tool points at the **local** SearXNG (another `host.openshell.internal:<port>` entry in the proxy allowlist), so from the sandbox's perspective the agent only ever talks to a service *inside the lab*. SearXNG then makes the real outbound call.

**What this buys you:** one controlled egress chokepoint you own and can log; queries carry **no commercial account or identifier** tying them to ICFO/QNOE; SearXNG strips identifying headers and can rotate which engines it uses; you can audit or block queries in one place.

**The crucial limit — read this carefully:** SearXNG anonymises **who** is asking, *not* **what** is asked. The **query text itself still leaves the network** and reaches the public engines. If the model puts `"unpublished BSCCO Tc 92K sample SLG07"` into a search, that phrase still lands at Google — SearXNG only hides that it came from this lab. So Option 3 solves *attribution/identity* leakage, **not** *content* leakage. That distinction is the whole reason it's "partial" privacy and why it sits above Option 2's risk but below a frontier provider's.

### Option 4 — Frontier-provider search
Route search through a commercial LLM's tool (B4 infrastructure). Highest capability, but query strings **and** surrounding context go to an external vendor. Deliberately deferred; only revisit as an explicit separate decision.

## Recommendation

Approve **Option 2 (allowlisted literature fetch) as a reversible, fully-logged pilot** — every outbound request posted to the Agent Logs channel, one-line rollback (same pattern as the sandbox). It respects the founding constraint instead of trading it away, and rides on infrastructure already in place. Keep **Options 3 and 4 explicitly deferred** pending a later call if fetch-only proves too limiting — Option 3 in particular should only be approved once everyone understands that query *content* still egresses.

*Rollback / audit note: whatever is enabled must (1) log every outbound query to Agent Logs and (2) be revertible by removing the host(s) from `network_policies` + disabling the toolset — no rebuild.*
