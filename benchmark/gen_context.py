#!/usr/bin/env python3
"""Generate the real injected context blocks for the acceptance suite,
reproducing what qnoe_rag.prefetch() would inject (RAG chunks + QCoDeS
registry block), offline. Mem0 is disabled here (per-user facts are not part
of these acceptance cases).

Run in the hermes-venv with:
  PYTHONPATH=/opt/qnoe-agent AGENT_DATA_DIR=/home/yzamir/qnoe_server_data \
  MEM0_ENABLED=0 hermes-venv/bin/python gen_context.py --out /tmp/accept_ctx.json
"""
import argparse
import importlib.util
import json
import os

os.environ.setdefault("MEM0_ENABLED", "0")
os.environ.setdefault("AGENT_DATA_DIR", "/home/yzamir/qnoe_server_data")

PLUGIN = "/opt/qnoe-agent/hermes/plugins/qnoe_rag/__init__.py"


def load_rag():
    spec = importlib.util.spec_from_file_location("qnoe_rag_offline", PLUGIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_block(rag, query, collections):
    chunks = rag._run_retrieve(query, collections)
    rag_txt = rag._format_chunks(chunks)
    rag_block = f"## RAG Context\n{rag_txt}" if rag_txt else ""
    qc = ""
    try:
        qc = rag._qcodes_registry_block(query)
    except Exception as e:
        qc = f"[registry err: {e}]"
    return (qc + rag_block), len(chunks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/accept_ctx.json")
    args = ap.parse_args()
    rag = load_rag()
    qtm = rag.PROFILE_COLLECTIONS["qnoe-qtm"]

    cases = {}

    # Case 1 — registry honoring, run 75000 (expected: does not exist)
    q1 = "What is in QCoDeS run 75000? Show me its parameters."
    b1, n1 = build_block(rag, q1, qtm)
    cases["case1_registry"] = {"question": q1, "context": b1, "n_chunks": n1}

    # Case 2 — QTM band structure
    q2 = "How does the QTM measure the electronic band structure?"
    b2, n2 = build_block(rag, q2, qtm)
    cases["case2_bandstructure"] = {"question": q2, "context": b2, "n_chunks": n2}

    # Case 3 — last gate sweep in QTM room-T setup (generic; must not invent)
    q3 = ("What is the last gate sweep measurement done in the QTM "
          "room-T setup?")
    b3, n3 = build_block(rag, q3, qtm)
    cases["case3_gatesweep"] = {"question": q3, "context": b3, "n_chunks": n3}

    for k, v in cases.items():
        print(f"{k}: n_chunks={v['n_chunks']} ctx_chars={len(v['context'])}")

    with open(args.out, "w") as f:
        json.dump(cases, f, indent=2)
    print(f"[written {args.out}]")


if __name__ == "__main__":
    main()
