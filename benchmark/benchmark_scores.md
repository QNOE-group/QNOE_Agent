# Hermes 3 70B Benchmark Scores
*Date: 2026-06-08 | Model: NousResearch Hermes-3-Llama-3.1-70B AWQ Marlin | vLLM 0.22.1*
*Score each run 1–5 on three criteria:*
- **C** — Correctness (is the answer right?)
- **R** — Reasoning quality (is the logic sound and clear?)
- **H** — Hallucination (5 = none, 1 = significant fabrication)

*Decision gate: mean score across all tasks < 3.5 → evaluate BF16 with cpu-offload or Hermes 3 8B for sub-agents*

---

## T1 — Code Review

| Run | C | R | H | Notes |
|---|---|---|---|---|
| 1 | 2 | 3 | 2 | Hallucinated `['value']` QCoDeS key; missed units bug (V/nA = GΩ) |
| 2 | 2 | 3 | 3 | Cleaner reasoning; still missed units bug |
| 3 | 2 | 3 | 3 | Best of three; kept correct vg access; still missed units bug |

**Task mean — C: 2.0 | R: 3.0 | H: 2.67 | Overall: 2.56**

## T2 — Data Analysis Reasoning

| Run | C | R | H | Notes |
|---|---|---|---|---|
| 1 | 2 | 3 | 3 | Wrong carrier density formula (dRxy/dVg dimensionally incorrect) |
| 2 | 4 | 4 | 4 | Correct formulas, best overall; misses anomalous QHE filling factors |
| 3 | 3 | 4 | 3 | Slight hallucination: mentions fractional QHE not expected at 5T in MLG |

**Task mean — C: 3.0 | R: 3.67 | H: 3.33 | Overall: 3.33**

## T3 — Literature Question (Physics)

| Run | C | R | H | Notes |
|---|---|---|---|---|
| 1 | 3 | 3 | 4 | Correct superfluidity mention; misses energy blueshift; Hopfield explanation incomplete |
| 2 | 3 | 4 | 4 | Most detailed; misses energy blueshift; arguable claim excitonic fraction "hinders" condensation |
| 3 | 3 | 3 | 4 | Solid but shallow; misses blueshift and superfluidity |

**Task mean — C: 3.0 | R: 3.33 | H: 4.0 | Overall: 3.44**

## T4 — Multi-step Plan

| Run | C | R | H | Notes |
|---|---|---|---|---|
| 1 | 3 | 4 | 4 | Fork workflow wrong for group member with direct repo access |
| 2 | 4 | 4 | 5 | Best — correct clone workflow, most complete, branch cleanup included |
| 3 | 4 | 4 | 5 | Hedges fork correctly ("if you don't have write access"); good structure |

**Task mean — C: 3.67 | R: 4.0 | H: 4.67 | Overall: 4.11**

## T5 — Tool Call

| Run | C | R | H | Notes |
|---|---|---|---|---|
| 1 | 4 | 4 | 5 | Correct fields; added unrequested wrapper; parameter "Hall resistance" vs "Rxy" ambiguous |
| 2 | 4 | 4 | 5 | Identical to Run 1 |
| 3 | 3 | 4 | 5 | Missing closing `}` — malformed JSON |

**Task mean — C: 3.67 | R: 4.0 | H: 5.0 | Overall: 4.22**

---

## Summary

| Task | Mean C | Mean R | Mean H | Mean Overall |
|---|---|---|---|---|
| T1 Code review | 2.0 | 3.0 | 2.67 | 2.56 |
| T2 Data reasoning | 3.0 | 3.67 | 3.33 | 3.33 |
| T3 Physics question | 3.0 | 3.33 | 4.0 | 3.44 |
| T4 Multi-step plan | 3.67 | 4.0 | 4.67 | 4.11 |
| T5 Tool call | 3.67 | 4.0 | 5.0 | 4.22 |
| **OVERALL** | **3.07** | **3.60** | **3.93** | **3.53** |

**Decision: PASS** (threshold: mean overall ≥ 3.5 — achieved 3.53)

**Recommendation:** Proceed with Hermes 3 70B AWQ Marlin as the primary model. Weakest area is domain-specific code review (T1: 2.56) — the model missed the physics units bug (V/nA = GΩ) consistently. For code review tasks, consider adding explicit unit-checking instructions to the system prompt. Strongest areas are structured task planning (T4) and tool calling (T5), which are core agent capabilities.

---

## Timing Summary

| Task | Avg latency | Avg tok/s |
|---|---|---|
| T1 Code review | ~62s | 6.4 |
| T2 Data reasoning | ~80s | 6.4 |
| T3 Physics question | ~93s | 6.4 |
| T4 Multi-step plan | ~96s | 6.4 |
| T5 Tool call | ~10s | 6.3 |

Generation throughput is consistently ~6.4 tok/s across all tasks on the GB10 with AWQ Marlin quantization.

---

## Full Responses and Analysis

---

### T1 — Code Review

**Question sent to model:**

> Review the following Python data-loading script and identify all bugs. Explain each bug clearly and provide a corrected version.
>
> ```python
> import qcodes as qc
> import numpy as np
>
> def load_measurement(run_id, db_path):
>     qc.initialise_or_create_database_at(db_path)
>     dataset = qc.load_by_id(run_id)
>     data = dataset.get_parameter_data()
>     # Extract gate voltage and current
>     vg = data['current']['gate_voltage']
>     current = data['gate_voltage']['current']
>     # Normalise current to nA
>     current_nA = current * 1e9
>     # Compute resistance
>     resistance = vg / current_nA
>     return vg, current_nA, resistance
> ```

**Intended bugs:**
1. `current = data['gate_voltage']['current']` — `gate_voltage` is not a top-level key in `get_parameter_data()`; should be `data['current']['current']`
2. `resistance = vg / current_nA` — units error: V / nA = GΩ, not Ω; should divide by `current` (in amps)

**Run 1 response:**
> There are two bugs in the provided Python data-loading script. I will explain each bug and provide a corrected version of the script.
>
> Bug 1: Incorrect parameter names when extracting gate voltage and current
> The script attempts to extract gate voltage and current data from the 'data' dictionary. However, the keys used to access the data are incorrect. The keys should be swapped: 'gate_voltage' should be used to access the voltage data, and 'current' should be used to access the current data.
>
> Corrected code:
> ```python
> vg = data['gate_voltage']['value']
> current = data['current']['value']
> ```
>
> Bug 2: Division by zero risk when computing resistance
> When computing the resistance, there is a risk of dividing by zero if the current is zero at any point. This can lead to undefined behavior or runtime errors. To avoid this issue, you can use numpy's `divide` function, which allows you to handle division by zero.
>
> Corrected code:
> ```python
> resistance = np.divide(vg, current_nA)
> ```

**Run 2 response:**
> There are two bugs in the provided Python data-loading script. I will explain each bug and provide a corrected version of the script.
>
> Bug 1: Incorrect parameter data retrieval
> The script attempts to extract gate voltage and current data, but the data retrieval is incorrect. The `get_parameter_data()` function returns a dictionary with keys corresponding to the measured parameters. In this case, the keys should be 'gate_voltage' and 'current'. The current implementation attempts to access the data incorrectly, resulting in a KeyError.
>
> Corrected code:
> ```python
> vg = data['gate_voltage']
> current = data['current']
> ```
>
> Bug 2: Division by zero
> The script computes the resistance by dividing the gate voltage by the normalized current. However, there is no check to ensure that the current is non-zero. This will result in a ZeroDivisionError.

**Run 3 response:**
> There are two bugs in the provided Python data-loading script. Here's the corrected version with explanations for each bug:
>
> Bug 1: Incorrect dictionary key
> The line `current = data['gate_voltage']['current']` is incorrect because it tries to access the 'current' key within the 'gate_voltage' dictionary. The corrected line is `current = data['current']`.
>
> Bug 2: Division by zero
> In some cases, the `current` array may contain zero values, which would result in a division by zero error when computing the resistance.

**Judgment:**
All three runs found some version of the key access bug. All three invented a "division by zero" bug not in the original. All three missed the units bug (V/nA = GΩ). Run 1 hallucinated a `['value']` key that does not exist in the QCoDeS API. The units error is the most physics-relevant bug and was missed consistently — this is a meaningful weakness for lab code review.

---

### T2 — Data Analysis Reasoning

**Question sent to model:**

> I have a 2D transport measurement of a graphene Hall bar device. The dataset contains: gate voltage Vg swept from -60V to +60V, longitudinal resistance Rxx and Hall resistance Rxy measured simultaneously at T=1.6K in magnetic fields B = 0, 1, 2, 3, 4, 5 T. The device shows a clear Dirac point near Vg = +5V. Describe a step-by-step analysis plan to extract the carrier density, mobility, and check for quantum Hall signatures.

**Run 1 response (excerpt):**
> Step 4: Calculating carrier density
> n = (1/e) * (dRxy/dVg)

**Run 2 response (excerpt):**
> Step 3: Calculate the carrier density
> n = Cg * (Vg - VDirac) / e
> where Cg is the gate capacitance per unit area...
>
> Step 5: Analyze the quantum Hall signatures
> Rxy = h / (e^2 * ν)

**Run 3 response (excerpt):**
> Step 3: Calculate the carrier density
> n = (1/e) * (B/Rxy)
>
> Step 6: Determine the quantum Hall filling factors
> ν = n * h / (e * B)

**Judgment:**
Run 1 has a dimensionally incorrect carrier density formula. Run 2 is the strongest — uses the correct gate capacitance approach and the right QHE formula. Run 3 uses the correct Hall formula for carrier density. All three miss the anomalous QHE filling factors specific to graphene (ν = ±2, ±6, ±10... due to Berry phase and 4-fold degeneracy). Run 3 incorrectly mentions fractional QHE which is not expected at 5T in monolayer graphene.

---

### T3 — Literature Question (Polariton Physics)

**Question sent to model:**

> Explain the concept of polariton condensation in a 2D semiconductor microcavity. What are the key experimental signatures that distinguish a polariton condensate from a photon laser? What role does the Hopfield coefficient play?

**Judgment (all three runs):**
All three correctly explain polariton formation, BEC analogy, and Hopfield coefficients controlling effective mass and interaction strength. All three correctly mention spatial coherence and linewidth narrowing as signatures. Key omissions across all runs: (1) the energy blueshift with increasing density — the most unambiguous distinguishing signature between condensate and laser; (2) occurrence below the photon lasing threshold; (3) graphene-specific anomalous QHE filling factors (not applicable here but noted for T2). Run 2 is the most detailed and mentions the competing roles of photonic and excitonic Hopfield components. Run 1 correctly mentions superfluidity (a strong distinguishing feature). Run 3 has the clearest threshold description.

---

### T4 — Multi-step Plan

**Question sent to model:**

> I want to add a new Jupyter notebook to our group's GitHub repository that analyses Landau fan diagrams from magnetotransport measurements. The repo uses Python, QCoDeS for data loading, and stores notebooks in an 'analysis/' folder. Other notebooks follow a standard header with imports, a 'load data' section, an 'analysis' section, and a 'figures' section. Outline the exact steps to create, document, and submit this notebook for review, including the git workflow.

**Judgment:**
All three responses correctly cover: branch creation, notebook structure, QCoDeS usage, git add/commit/push, PR, and review cycle. Runs 1 and 3 suggest forking the repository — incorrect for a group member with direct write access to the QNOE-group org (our workflow is branch → PR, not fork → PR). Run 2 is the strongest: starts with direct clone, includes `git push -u origin`, mentions branch cleanup after merge, and suggests markdown cells for documentation. Run 3 partially recovers by hedging with "if you don't already have write access."

---

### T5 — Tool Call

**Question sent to model:**

> You have access to the following function:
>
> `get_measurement_runs(device_id: str, start_date: str, end_date: str, parameter: str) -> list[dict]`
> Returns a list of measurement runs for a device within a date range filtered by parameter name.
>
> A researcher asks: 'Show me all Hall resistance measurements for device BLG-07 from January to March 2026.'
>
> Respond with only the function call in JSON format, nothing else.

**Expected output:**
```json
{
  "device_id": "BLG-07",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31",
  "parameter": "Rxy"
}
```

**All three runs returned (identical for runs 1 and 2):**
```json
{
  "function": "get_measurement_runs",
  "arguments": {
    "device_id": "BLG-07",
    "start_date": "2026-01-01",
    "end_date": "2026-03-31",
    "parameter": "Hall resistance"
  }
}
```

**Run 3 was identical but missing the closing `}`.**

**Judgment:**
All fields correct. Two minor issues: (1) added a `function`/`arguments` wrapper not requested — reflects OpenAI tool-calling conventions, defensible; (2) `"parameter": "Hall resistance"` vs the expected `"Rxy"` — reasonable interpretation of the researcher's natural language, but in a real QCoDeS database the exact parameter string matters. Run 3 produced malformed JSON (missing closing brace), which would break any downstream parser.
