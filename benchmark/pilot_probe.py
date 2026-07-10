#!/usr/bin/env python3
"""gpt-oss pilot probe harness.

Measures, against an OpenAI-compatible endpoint:
  1. decode tok/s on a 400-token generation (3x, temp 0)
  2. TTFT on a ~10K-token prompt (3x)
  3. structured tool-calling vs context length (~400 / 10K / 20K / 40K)

Usage:
  python pilot_probe.py --model <id> --base-url http://localhost:8000/v1 \
      [--tag hermes3|gptoss] [--out /tmp/probe_<tag>.md]
"""
import argparse
import json
import sys
import time
import urllib.request

FILLER_SENTENCE = (
    "In the quantum twisting microscope a sharp graphene tip is brought into "
    "contact with a target two dimensional crystal and the twist angle between "
    "them is varied in situ while the tunneling current is recorded. "
)


def _post(base_url, payload, timeout=600):
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer no-key"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    return body, time.time() - t0


def _post_stream_ttft(base_url, payload, timeout=600):
    payload = dict(payload, stream=True)
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer no-key"},
    )
    t0 = time.time()
    ttft = None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except Exception:
                continue
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            if delta.get("content") or delta.get("reasoning_content"):
                ttft = time.time() - t0
                break
    return ttft


def make_filler(approx_tokens):
    # ~ 4 chars per token; FILLER_SENTENCE ~ 46 tokens
    reps = max(1, approx_tokens // 46)
    return FILLER_SENTENCE * reps


def bench_decode(base_url, model, n=3):
    out = []
    for i in range(n):
        payload = {
            "model": model,
            "messages": [{"role": "user",
                          "content": "Write exactly 400 words about graphene. "
                                     "Do not stop early."}],
            "max_tokens": 450, "temperature": 0,
        }
        body, wall = _post(base_url, payload)
        ct = body["usage"]["completion_tokens"]
        out.append((ct, wall, ct / wall if wall else 0))
    return out


def bench_ttft(base_url, model, ctx_tokens=10000, n=3):
    filler = make_filler(ctx_tokens)
    out = []
    for i in range(n):
        payload = {
            "model": model,
            "messages": [
                {"role": "user",
                 "content": filler + "\n\nSummarize the above in one sentence."}],
            "max_tokens": 30, "temperature": 0,
        }
        ttft = _post_stream_ttft(base_url, payload)
        out.append(ttft)
    return out


TOOLS = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the contents of a file from disk.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path."}
            },
            "required": ["path"],
        },
    },
}]


def probe_toolcall(base_url, model, ctx_tokens):
    filler = make_filler(ctx_tokens) if ctx_tokens > 500 else ""
    instr = ("You must read the file /etc/hostname to answer. "
             "Call the read_file tool with path=/etc/hostname now.")
    content = (filler + "\n\n" + instr) if filler else instr
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "tools": TOOLS, "tool_choice": "auto",
        "max_tokens": 200, "temperature": 0,
    }
    try:
        body, wall = _post(base_url, payload)
    except Exception as e:
        return {"ctx": ctx_tokens, "ok": False, "err": str(e)[:200]}
    choice = body["choices"][0]
    fr = choice.get("finish_reason")
    tc = choice["message"].get("tool_calls")
    prompt_toks = body["usage"]["prompt_tokens"]
    ok = bool(tc) and fr == "tool_calls"
    name = tc[0]["function"]["name"] if tc else None
    args = tc[0]["function"]["arguments"] if tc else None
    return {"ctx": ctx_tokens, "prompt_tokens": prompt_toks, "ok": ok,
            "finish_reason": fr, "tool_name": name, "tool_args": args,
            "text_head": (choice["message"].get("content") or "")[:120]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--tag", default="model")
    ap.add_argument("--out", default=None)
    ap.add_argument("--skip-decode", action="store_true")
    args = ap.parse_args()

    lines = [f"# Pilot probe — {args.tag} ({args.model})", ""]

    if not args.skip_decode:
        dec = bench_decode(args.base_url, args.model)
        avg = sum(x[2] for x in dec) / len(dec)
        lines.append("## Decode (400-tok gen, 3x, temp 0)")
        for ct, wall, tps in dec:
            lines.append(f"- {ct} tok / {wall:.1f}s = {tps:.1f} tok/s")
        lines.append(f"- **mean decode: {avg:.1f} tok/s**")
        lines.append("")

        ttfts = bench_ttft(args.base_url, args.model)
        good = [t for t in ttfts if t]
        lines.append("## TTFT (~10K-token prompt, 3x)")
        for t in ttfts:
            lines.append(f"- {t:.2f}s" if t else "- (no token / err)")
        if good:
            lines.append(f"- **mean TTFT: {sum(good)/len(good):.2f}s**")
        lines.append("")

    lines.append("## Tool-call vs context length")
    lines.append("| ctx target | prompt_tokens | structured tool_call? | finish_reason | tool | args |")
    lines.append("|---|---|---|---|---|---|")
    for ctx in (400, 10000, 20000, 40000):
        r = probe_toolcall(args.base_url, args.model, ctx)
        if not r.get("ok") and r.get("err"):
            lines.append(f"| {ctx} | ERR | NO | - | - | {r['err']} |")
            continue
        mark = "YES" if r["ok"] else "**NO**"
        lines.append(
            f"| {ctx} | {r.get('prompt_tokens','?')} | {mark} | "
            f"{r.get('finish_reason')} | {r.get('tool_name')} | "
            f"{str(r.get('tool_args'))[:60]} |")
        if not r["ok"]:
            lines.append(f"|  |  | text_head: {r.get('text_head','')[:80]} |||||")
    lines.append("")

    report = "\n".join(lines)
    print(report)
    if args.out:
        with open(args.out, "w") as f:
            f.write(report + "\n")
        print(f"\n[written to {args.out}]")


if __name__ == "__main__":
    main()
