"""QNOE research-program ontology as a Cognee `graph_model` (COGNEE_ONTOLOGY.md).

cognee 0.5.6 `cognify(graph_model=…)` expects a `KnowledgeGraph`-shaped Pydantic
model: `{nodes: [{id,name,type,description}], edges: [{source_node_id,
target_node_id, relationship_name}]}`. We enforce the ontology by constraining
`type` and `relationship_name` to Literal enums — the extractor (via instructor)
must pick from OUR types, so it cannot invent node kinds. This is the prescribed
tier; instances are learned.
"""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field

# Tier 1 (factual anchor) + Tier 2 (research/conceptual) node types.
NodeType = Literal[
    # Tier 1
    "Person", "Subteam", "Setup", "Sample", "Experiment", "Run", "MeasurementType",
    # Tier 2
    "Material", "Concept", "Phenomenon", "Technique", "PhysicalQuantity",
    "ResearchQuestion", "Project", "Finding", "Publication",
]

RelName = Literal[
    # factual
    "performed_by", "on_sample", "on_setup", "measured_on", "is_type",
    "swept", "measured", "member_of", "made_of", "owned_by", "contains",
    "part_of", "enables",
    # research
    "studies", "investigates", "pursues", "uses", "probes", "runs_on",
    "exhibits", "described_by", "related_to", "motivated_by", "refines",
    "addresses", "reports", "authored_by", "cites", "supports", "refutes",
    "works_on", "expert_in", "builds_on",
]


class QNode(BaseModel):
    id: str = Field(description="stable lowercase slug, e.g. 'momentum-resolved-tunneling'")
    name: str = Field(description="canonical human-readable name")
    type: NodeType
    description: str = Field(default="", description="one sentence, grounded in the source text")


class QEdge(BaseModel):
    source_node_id: str
    target_node_id: str
    relationship_name: RelName


class QKnowledgeGraph(BaseModel):
    nodes: List[QNode] = Field(default_factory=list)
    edges: List[QEdge] = Field(default_factory=list)


# Domain guidance appended to cognee's extraction prompt (custom_prompt).
CUSTOM_PROMPT = """You are building a knowledge graph of the QNOE group's RESEARCH PROGRAM
(ICFO, Barcelona; PI Frank Koppens) — quantum optics/electronics with 2D materials
(graphene, hBN, MoO3, BSCCO), and specifically the Quantum Twisting Microscope (QTM/QTOM).

Extract the research the text is about — NOT a summary. Use ONLY the provided node
types and relationship names. Capture:
- Concept / Phenomenon (e.g. moiré flat bands, momentum-resolved tunneling, photothermoelectric effect)
- ResearchQuestion the work pursues; Project / effort; Finding; Publication
- Technique / Method and the Setup / instrument it runs on; Material; PhysicalQuantity (control knobs & observables)
- factual anchors when named: Person, Sample, Experiment, Run, MeasurementType

Rules:
- Prefer linking new nodes to entities already in the graph (setups, samples, materials).
- Ground every node in the text; do NOT invent concepts, numbers, or relationships not supported by the source.
- Give each node a stable lowercase-slug id and reuse it for the same entity across documents.
"""
