"""Run only T4 and T5 from the benchmark."""
import sys
sys.path.insert(0, '/home/yzamir/qnoe-agent/benchmark')
from run_benchmark import TASKS, call_model, RUNS_PER_TASK

for task_id in ["T4_multi_step_plan", "T5_tool_call"]:
    task = TASKS[task_id]
    print(f"\n{'='*60}\nTask: {task_id} — {task['description']}\n{'='*60}")
    for run in range(1, RUNS_PER_TASK + 1):
        print(f"\n  Run {run}/{RUNS_PER_TASK}... ", end="", flush=True)
        result = call_model(task["prompt"])
        print(f"{result['latency_s']}s | {result['tokens_per_second']} tok/s | {result['completion_tokens']} tokens")
        print(f"\n  RESPONSE:\n{result['response']}\n")
