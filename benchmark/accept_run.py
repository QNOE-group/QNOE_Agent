#!/usr/bin/env python3
"""Acceptance + benchmark answer generator.

Runs the QTM SOUL system prompt + injected context (from gen_context.py) for
acceptance cases 1-3, plus the benchmark T1-T5 suite and smoke questions,
against an OpenAI-compatible endpoint. Emits raw answers to markdown for manual
rubric scoring.

Usage:
  python accept_run.py --model <id> --soul /tmp/qtm_soul.md \
      --ctx /tmp/accept_ctx.json --tag gptoss --out /tmp/accept_gptoss.md
"""
import argparse
import json
import time
import urllib.request


def chat(base_url, model, system, user, max_tokens=1200, timeout=900):
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens, "temperature": 0,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer no-key"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    wall = time.time() - t0
    msg = body["choices"][0]["message"]
    usage = body.get("usage", {})
    return {
        "content": msg.get("content") or "",
        "reasoning": msg.get("reasoning_content") or "",
        "wall": wall,
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
    }


BENCH = {
    "T1_code_review": (
        "Review the following Python data-loading script and identify all bugs. "
        "Explain each bug clearly and provide a corrected version.\n\n"
        "```python\nimport qcodes as qc\nimport numpy as np\n\n"
        "def load_measurement(run_id, db_path):\n"
        "    qc.initialise_or_create_database_at(db_path)\n"
        "    dataset = qc.load_by_id(run_id)\n"
        "    data = dataset.get_parameter_data()\n"
        "    # Extract gate voltage and current\n"
        "    vg = data['current']['gate_voltage']\n"
        "    current = data['gate_voltage']['current']\n"
        "    # Normalise current to nA\n"
        "    current_nA = current * 1e9\n"
        "    # Compute resistance\n"
        "    resistance = vg / current_nA\n"
        "    return vg, current_nA, resistance\n```"),
    "T2_data_reasoning": (
        "I have a 2D transport measurement of a graphene Hall bar device. The "
        "dataset contains: gate voltage Vg swept from -60V to +60V, longitudinal "
        "resistance Rxx and Hall resistance Rxy measured simultaneously at T=1.6K "
        "in magnetic fields B = 0, 1, 2, 3, 4, 5 T. The device shows a clear Dirac "
        "point near Vg = +5V. Describe a step-by-step analysis plan to extract the "
        "carrier density, mobility, and check for quantum Hall signatures."),
    "T3_physics": (
        "Explain the concept of polariton condensation in a 2D semiconductor "
        "microcavity. What are the key experimental signatures that distinguish a "
        "polariton condensate from a photon laser? What role does the Hopfield "
        "coefficient play?"),
    "T4_plan": (
        "I want to add a new Jupyter notebook to our group's GitHub repository "
        "that analyses Landau fan diagrams from magnetotransport measurements. The "
        "repo uses Python, QCoDeS for data loading, and stores notebooks in an "
        "'analysis/' folder. Other notebooks follow a standard header with imports, "
        "a 'load data' section, an 'analysis' section, and a 'figures' section. "
        "Outline the exact steps to create, document, and submit this notebook for "
        "review, including the git workflow."),
    "T5_tool_call": (
        "You have access to the following function:\n\n"
        "`get_measurement_runs(device_id: str, start_date: str, end_date: str, "
        "parameter: str) -> list[dict]`\nReturns a list of measurement runs for a "
        "device within a date range filtered by parameter name.\n\nA researcher "
        "asks: 'Show me all Hall resistance measurements for device BLG-07 from "
        "January to March 2026.'\n\nRespond with only the function call in JSON "
        "format, nothing else."),
}

SMOKE = {
    "smoke1_physics": (
        "In one paragraph: why does hBN make a good substrate and gate dielectric "
        "for graphene devices?"),
    "smoke2_coding": (
        "Write a short Python function using numpy that computes the numerical "
        "derivative dRxy/dB from arrays B and Rxy, returning the array of "
        "derivatives."),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--soul", required=True)
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--tag", default="model")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.soul) as f:
        soul = f.read()
    with open(args.ctx) as f:
        ctx = json.load(f)

    out = [f"# Acceptance + benchmark answers — {args.tag} ({args.model})", ""]

    # Acceptance cases 1-3 (SOUL + injected context)
    for key in ("case1_registry", "case2_bandstructure", "case3_gatesweep"):
        c = ctx[key]
        system = soul + "\n\n" + c["context"]
        out.append(f"## {key}")
        out.append(f"**Question:** {c['question']}")
        out.append(f"**Injected context chars:** {len(c['context'])} "
                   f"(n_chunks={c['n_chunks']})")
        r = chat(args.base_url, args.model, system, c["question"])
        out.append(f"**Answer** ({r['wall']:.1f}s, "
                   f"{r['completion_tokens']} tok, "
                   f"prompt {r['prompt_tokens']} tok):")
        out.append("")
        out.append(r["content"].strip() or "(empty content)")
        if r["reasoning"]:
            out.append("")
            out.append("<reasoning>")
            out.append(r["reasoning"].strip()[:1500])
            out.append("</reasoning>")
        out.append("")

    # Benchmark T1-T5 (standalone, SOUL as system)
    for key, q in BENCH.items():
        out.append(f"## {key}")
        r = chat(args.base_url, args.model, soul, q)
        out.append(f"**Answer** ({r['wall']:.1f}s, {r['completion_tokens']} tok):")
        out.append("")
        out.append(r["content"].strip() or "(empty content)")
        out.append("")

    # Smoke
    for key, q in SMOKE.items():
        out.append(f"## {key}")
        r = chat(args.base_url, args.model, soul, q)
        out.append(f"**Answer** ({r['wall']:.1f}s):")
        out.append("")
        out.append(r["content"].strip() or "(empty content)")
        out.append("")

    report = "\n".join(out)
    with open(args.out, "w") as f:
        f.write(report + "\n")
    print(f"[written {args.out}] ({len(report)} chars)")


if __name__ == "__main__":
    main()
