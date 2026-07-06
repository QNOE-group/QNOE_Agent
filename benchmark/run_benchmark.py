"""
Hermes 3 70B inference benchmark — QNOE lab tasks
Run: python run_benchmark.py
Results saved to benchmark_results.json
Score each response manually (1-5) and fill in benchmark_scores.md
"""

import json
import time
import urllib.request
from datetime import datetime

ENDPOINT = "http://127.0.0.1:8000/v1/chat/completions"
MODEL = "/home/yzamir/qnoe-agent/models/hermes-3-70b-awq"

TASKS = {
    "T1_code_review": {
        "description": "Python code review — find bugs in a QCoDeS-style script",
        "prompt": (
            "Review the following Python data-loading script and identify all bugs. "
            "Explain each bug clearly and provide a corrected version.\n\n"
            "```python\n"
            "import qcodes as qc\n"
            "import numpy as np\n\n"
            "def load_measurement(run_id, db_path):\n"
            "    qc.initialise_or_create_database_at(db_path)\n"
            "    dataset = qc.load_by_id(run_id)\n"
            "    data = dataset.get_parameter_data()\n"
            "    # Extract gate voltage and current\n"
            "    vg = data['current']['gate_voltage']\n"  # bug 1: wrong key order
            "    current = data['gate_voltage']['current']\n"  # bug 2: wrong key order
            "    # Normalise current to nA\n"
            "    current_nA = current * 1e9\n"
            "    # Compute resistance\n"
            "    resistance = vg / current_nA\n"  # bug 3: should be vg / current (not nA)
            "    return vg, current_nA, resistance\n"
            "```"
        ),
    },
    "T2_data_reasoning": {
        "description": "Data analysis reasoning — measurement dataset analysis plan",
        "prompt": (
            "I have a 2D transport measurement of a graphene Hall bar device. "
            "The dataset contains: gate voltage Vg swept from -60V to +60V, "
            "longitudinal resistance Rxx and Hall resistance Rxy measured simultaneously "
            "at T=1.6K in magnetic fields B = 0, 1, 2, 3, 4, 5 T. "
            "The device shows a clear Dirac point near Vg = +5V. "
            "Describe a step-by-step analysis plan to extract the carrier density, "
            "mobility, and check for quantum Hall signatures."
        ),
    },
    "T3_literature_question": {
        "description": "Physics question — QED/polariton physics",
        "prompt": (
            "Explain the concept of polariton condensation in a 2D semiconductor microcavity. "
            "What are the key experimental signatures that distinguish a polariton condensate "
            "from a photon laser? What role does the Hopfield coefficient play?"
        ),
    },
    "T4_multi_step_plan": {
        "description": "Multi-step plan — add analysis notebook to a repo",
        "prompt": (
            "I want to add a new Jupyter notebook to our group's GitHub repository that analyses "
            "Landau fan diagrams from magnetotransport measurements. The repo uses Python, "
            "QCoDeS for data loading, and stores notebooks in an 'analysis/' folder. "
            "Other notebooks follow a standard header with imports, a 'load data' section, "
            "an 'analysis' section, and a 'figures' section. "
            "Outline the exact steps to create, document, and submit this notebook for review, "
            "including the git workflow."
        ),
    },
    "T5_tool_call": {
        "description": "Tool call — invoke mock function with correct JSON arguments",
        "prompt": (
            "You have access to the following function:\n\n"
            "```\n"
            "get_measurement_runs(device_id: str, start_date: str, end_date: str, "
            "parameter: str) -> list[dict]\n"
            "Returns a list of measurement runs for a device within a date range "
            "filtered by parameter name.\n"
            "```\n\n"
            "A researcher asks: 'Show me all Hall resistance measurements for device BLG-07 "
            "from January to March 2026.'\n\n"
            "Respond with only the function call in JSON format, nothing else."
        ),
    },
}

RUNS_PER_TASK = 3


def call_model(prompt: str) -> dict:
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }).encode()

    req = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t_start = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        t_end = time.time()
        result = json.loads(resp.read())

    latency = round(t_end - t_start, 2)
    content = result["choices"][0]["message"]["content"]
    tokens = result["usage"]["completion_tokens"]

    return {
        "latency_s": latency,
        "completion_tokens": tokens,
        "tokens_per_second": round(tokens / latency, 1),
        "response": content,
    }


def main():
    print(f"QNOE Hermes 3 70B Benchmark — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Endpoint: {ENDPOINT}")
    print(f"Tasks: {len(TASKS)} × {RUNS_PER_TASK} runs\n")

    results = {}

    for task_id, task in TASKS.items():
        print(f"\n{'='*60}")
        print(f"Task: {task_id} — {task['description']}")
        print('='*60)
        results[task_id] = {"description": task["description"], "runs": []}

        for run in range(1, RUNS_PER_TASK + 1):
            print(f"\n  Run {run}/{RUNS_PER_TASK}... ", end="", flush=True)
            result = call_model(task["prompt"])
            results[task_id]["runs"].append(result)
            print(f"{result['latency_s']}s | {result['tokens_per_second']} tok/s | {result['completion_tokens']} tokens")
            print(f"\n  RESPONSE:\n{result['response']}\n")

    # Save results
    out_path = "benchmark_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print("TIMING SUMMARY")
    print('='*60)
    for task_id, data in results.items():
        latencies = [r["latency_s"] for r in data["runs"]]
        tps = [r["tokens_per_second"] for r in data["runs"]]
        print(f"{task_id}: avg {round(sum(latencies)/len(latencies), 1)}s | avg {round(sum(tps)/len(tps), 1)} tok/s")

    print(f"\nFull results saved to {out_path}")
    print("Score each response (1-5) in benchmark_scores.md")


if __name__ == "__main__":
    main()
