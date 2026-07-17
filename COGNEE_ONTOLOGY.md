# QNOE Knowledge-Graph Ontology (Cognee)

*Created: 2026-07-17. Companion to [[COGNEE_PLAN]]. Status: design — the prescribed schema for the corpus KG.*

The ontology has **two tiers** ([[COGNEE_PLAN]] §0): **Tier 1 — factual anchor** (deterministic, from the registry/configs/filesystem, real ground truth) and **Tier 2 — research/conceptual** (LLM-extracted from prose, *inferred*, provenance-tagged). Both live in one Kùzu graph; Tier-2 nodes attach to the Tier-1 scaffold. It is **prescribed** (this schema constrains extraction) **+ learned** (extraction may add instances/relations within it).

---

## 0. Base — fields every node carries

```python
from cognee.infrastructure.engine import DataPoint
from pydantic import SkipValidation
from typing import Any, Optional, Literal

class QNode(DataPoint):
    name: str                              # canonical label
    aliases: list[str] = []                # synonyms / abbreviations (e.g. "BLG" = "bilayer graphene")
    description: str = ""
    tier: Literal[1, 2] = 2                # 1 = deterministic fact, 2 = LLM-inferred
    # provenance — REQUIRED for tier 2 (never assert inferred as fact):
    source_ref: str = ""                   # source doc URL/path (Tier-2) or registry key (Tier-1)
    extracted_by: str = ""                 # model+effort for Tier-2 (e.g. "gpt-oss-120b/high"); "" for Tier-1
    confidence: Optional[float] = None     # extractor confidence, if available
    metadata: dict = {"index_fields": ["name", "aliases", "description"]}
```

Everything below subclasses `QNode` (only the *distinctive* fields are listed). `index_fields` = what gets embedded for semantic search.

---

## 1. Tier 1 — Factual anchor (deterministic; NO LLM)

| Node | Purpose / QNOE examples | Distinctive fields | Source |
|---|---|---|---|
| **Person** | group member | role, subteam, active_from/to | `user_profiles.yaml`, `maintainer.yaml`, `Notebook/<name>/` |
| **Subteam** | organizational unit — QTM, Photocurrent, QED, Superconductivity, QSIM, XCHIRAL | code, lead | SOULs / config |
| **Setup** | measurement rig — *L110 QTM*, *L206 Photocurrent*, *L208 Opticool*, *SpectroMag*, *THz laser*, *GRASP* | location, kind | db paths, `Setups/` |
| **Sample** | physical 2D device — *Tip5Sample9*, *BFNB4_D4* | folder_name, crystal_name, fab_date | registry `sample_name` + folder |
| **Experiment** | a measurement **campaign** = one *Person* × one *Sample* × one *Setup* over a period (≈ a `YYYY.MM_TipXSampleY` measurement folder); **groups Runs** | started_at, ended_at, folder | folder/db grouping + `Notebook/` owner |
| **Run** | one QCoDeS measurement (atomic) | run_id, db_path, run_name, exp_name, completed_at | QCoDeS registry (`add_data_points`) |
| **MeasurementType** | gate-sweep, IV, photocurrent-map, cooldown, spectroscopy | — | `run_name`/`exp_name` via `_TYPE_RULES` |
| **Dataset** | a `.db` file / data collection | db_path, n_runs | registry |
| **Repository** | a GitHub repo — *QTM_CodeBase*, *SLG07-PhQH*, *GRASP-Acquisition* | url, subteam | repo list |
| **Software** | analysis/acquisition tool/package — *Nbandstructure*, *GRASP-Analysis*, *MEEP* | language, repo | repo prose |

## 2. Tier 2 — Research / conceptual (LLM-extracted; provenance-tagged)

| Node | Purpose / QNOE examples | Distinctive fields | Notes |
|---|---|---|---|
| **Material** | material system — *graphene*, *bilayer graphene (BLG)*, *hBN*, *MoO₃*, *BSCCO*, *WSe₂*, *graphite tip* | formula, class (2D/vdW/SC) | **bridge** — physical & conceptual |
| **Concept** | a physics concept the group reasons with — *moiré flat bands*, *Berry curvature*, *hot carriers*, *momentum conservation*, *Landau levels*, *twist angle* | — | the vocabulary of the research |
| **Phenomenon** | a physical effect studied — *quantum Hall photocurrent*, *photothermoelectric effect*, *momentum-resolved tunneling*, *hyperbolic phonon-polaritons*, *unconventional superconductivity*, *non-local conductivity* | — | what experiments probe |
| **Technique** | experimental/computational method — *momentum-resolved tunneling spectroscopy*, *scanning photocurrent microscopy*, *nano-IR / s-SNOM*, *transport*, *MEEP FDTD*, *tight-binding band-structure* | kind (exp/comp) | how research is done |
| **PhysicalQuantity** | a control knob or observable — *gate voltage (Vg)*, *twist angle (θ)*, *temperature*, *wavelength*, *conductivity σ*, *responsivity*, *dispersion E(k)* | symbol, unit, role (control/observable) | **bridge** to registry params |
| **ResearchQuestion** | a question/theme pursued — **broad or specific** (merged: covers both the thrust *"momentum-resolved spectroscopy of 2D materials"* and the sharp *"how twist angle tunes tunneling momentum"*) | breadth (broad/specific), status (open/answered) | can `–refines→` another RQ for hierarchy |
| **Project** | a concrete effort — maps to repos/proposals (*SLG07-PhQH*, *BLG-QED*, *XCHIRAL*) | status, subteam, **hypothesis / claims** (the testable statements the project asserts) | **anchor↔research hinge**; absorbs Hypothesis |
| **Finding** | a concluded result/observation | status (claimed/published) | asserted with source; `–supports/refutes→ Project` |
| **Publication** | paper / internal manuscript — from `Papers_Books/`, `Manuscripts/` | year, venue, doi, status | Tier-2 metadata; may bridge |

---

## 3. Edge types (the relationships that make it a *research* graph)

Edges are `SkipValidation[Any]` fields (or `Edge(relationship_type=...)`), domain → range:

### Structural / factual (Tier 1)
- `Experiment –performed_by→ Person` · `Experiment –on_sample→ Sample` · `Experiment –on_setup→ Setup` · `Experiment –contains→ Run`
- `Run –part_of→ Experiment` · `Run –measured_on→ Sample` · `Run –on_setup→ Setup` · `Run –is_type→ MeasurementType` · `Run –swept→ PhysicalQuantity` · `Run –measured→ PhysicalQuantity`
- `Dataset –contains→ Run` · `Sample –made_of→ Material` · `Sample –owned_by / fabricated_by→ Person`
- `Person –member_of→ Subteam` · `Setup –enables→ Technique` · `Repository –belongs_to→ Project` · `Repository –implements→ Software` · `Software –computes→ Technique`

### Research-semantic (Tier 2)
- `Project –studies→ Concept | Phenomenon` · `Project –investigates→ Material` · `Project –pursues→ ResearchQuestion` · `Project –uses→ Technique`
- `Technique –probes→ Phenomenon` · `Technique –measures→ PhysicalQuantity` · `Technique –runs_on→ Setup`
- `Material –exhibits→ Phenomenon` · `Phenomenon –described_by→ Concept` · `Concept –related_to→ Concept`
- `ResearchQuestion –motivated_by→ Concept | Phenomenon` · `ResearchQuestion –refines→ ResearchQuestion` (broad↔specific hierarchy, replacing the old Direction/Question split)
- `Publication –addresses→ ResearchQuestion` · `Publication –reports→ Finding` · `Publication –uses→ Technique` · `Publication –studies→ Material | Phenomenon` · `Publication –authored_by→ Person` · `Publication –cites→ Publication`
- `Finding –supports | refutes→ Project` (the project's hypothesis/claims field)
- `Person –works_on→ Project` · `Person –expert_in→ Concept | Technique` · `Project –builds_on→ Project | Publication`

### ⭐ Cross-tier bridges (data ↔ research — the whole point)
The **Experiment** is the hinge: it carries the research intent that the atomic Run does not. These connect the deterministic anchor to the inferred research graph and let the KG answer "what research does this measurement serve":
- `Experiment –part_of→ Project` · `Experiment –tests→ Project` (the project's hypothesis) · `Experiment –probes→ Phenomenon` · `Experiment –uses→ Technique` · `Experiment –contributes_to→ ResearchQuestion`
- `Run –part_of→ Experiment` (atomic runs inherit the campaign's research context)
- `Sample –made_of→ Material –exhibits→ Phenomenon` (materials chain)
- `Setup –enables→ Technique –probes→ Phenomenon` (capability chain)

---

## 4. Worked subgraph (sanity check — the QTM twist-angle effort)

```
ResearchQuestion "momentum-resolved spectroscopy of 2D materials" (broad)
  └─refines→ ResearchQuestion "how twist angle tunes tunneling momentum" (specific)
        ▲ motivated_by
  Concept "moiré momentum boost"   Concept "momentum conservation"
Project "QTM twist-angle mapping" (repo QTM_CodeBase, subteam QTM; hypothesis: "θ scans k-space")
  ├─pursues→ (that ResearchQuestion)
  ├─uses→ Technique "momentum-resolved tunneling spectroscopy" ─runs_on→ Setup "L110 QTM"
  └─investigates→ Material "graphene" ─exhibits→ Phenomenon "momentum-resolved tunneling"
Experiment "2026.05 Tip5Sample9 on L110" ─performed_by→ Person X ─on_sample→ Sample "Tip5Sample9" ─on_setup→ Setup "L110 QTM"
  ├─part_of→ Project ; ─tests→ Project ; ─probes→ Phenomenon "momentum-resolved tunneling"
  └─contains→ Run 848 ─is_type→ MeasurementType "gate-sweep" ─swept→ PhysicalQuantity "gate voltage" ─measured_on→ Sample "Tip5Sample9" (made_of graphene)
Finding "θ-dependent E(k) observed" ─supports→ Project
Publication "Inbar et al., Nature 2023 (QTM)" ─addresses→ (that ResearchQuestion) ─uses→ (that Technique)
```

If Phase-0 extraction on QTOM docs produces *this shape* — concepts/questions/techniques correctly linked to setups, materials, and the real runs — it's working. If it invents concepts, mislinks techniques to wrong setups, or produces vague nodes, that's the confabulation failure the gate is for.

---

## 5. Extraction guidance (Tier 2 only)

- **Prescribe these types** to `cognify` (the graph model) so extraction can't invent arbitrary node kinds; allow *instances* to be learned, not new *types*.
- **Canonicalize + alias** aggressively: "BLG"="bilayer graphene", "Vg"="gate voltage", "QTM"="quantum twisting microscope" — dedup on aliases so the graph doesn't fragment.
- **Every Tier-2 node keeps `source_ref` + `extracted_by`** — the grounding oracle presents these as *inferred from <doc>*, never as fact.
- **Prefer linking to the anchor** over free-floating concepts: an extracted `Technique`/`Material`/`Phenomenon` should attach to an existing Tier-1 `Setup`/`Sample` where possible.

---

## 6. Extensions (defer past v1)

`Grant`/`FundingSource`, `ExternalCollaborator`/`Institution`, `Event` (talk/conference), `Instrument`-component granularity, temporal validity on research edges (Graphiti-style). Add only if a real query needs them.

---

*Full type set (revised 2026-07-17 per review — Experiment added, ResearchQuestion+ResearchDirection merged, Hypothesis folded into Project): Tier 1 — Person, Subteam, Setup, Sample, **Experiment**, Run, MeasurementType, Dataset, Repository, Software; Tier 2 — Material, Concept, Phenomenon, Technique, PhysicalQuantity, ResearchQuestion, Project, Finding, Publication.*

**QTOM pilot: extract the FULL Tier-2 set at once** (user decision 2026-07-17) — no v1 subsetting; run the whole ontology so the first read shows the real graph shape to judge.
