from typing import TypedDict, Literal, Optional

AgentID = Literal[
    "orchestrator", "qed", "superconductivity",
    "photocurrent", "qtm", "qsim", "xchiral",
]


class Message(TypedDict):
    role: Literal["user", "assistant", "tool"]
    content: str
    timestamp: str           # ISO 8601
    user_id: Optional[str]   # Teams user ID; None for agent-initiated


class TaskRecord(TypedDict):
    task_id: str
    task_type: str           # "code_review" | "analysis" | "pr_open" | ...
    repo: Optional[str]
    outcome: str             # "success" | "failed" | "cancelled"
    summary: str             # 1–2 sentence human-readable result
    timestamp: str


class ApprovalRequest(TypedDict):
    operation_id: str
    tier: int                # T2 | T3 | T4
    description: str
    manifest: Optional[str]  # JSON string; required for T4
    requested_at: str
    requested_by: str        # agent_id that triggered the action
    approve_by: list[str]    # Teams user IDs authorised to approve


class AgentState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────────────
    agent_id: AgentID
    session_id: str          # Teams conversation_id or thread_id
    active_user: Optional[str]
    active_channel: Optional[str]

    # ── Conversation ──────────────────────────────────────────────────────────
    messages: list[Message]
    conversation_summary: Optional[str]
    turns_since_summary: int

    # ── Current task ──────────────────────────────────────────────────────────
    current_task: Optional[dict]
    task_history: list[TaskRecord]

    # ── Approval (T2–T4; not used in Phase 1) ─────────────────────────────────
    pending_approval: Optional[ApprovalRequest]

    # ── Context assembled per turn (rebuilt each call) ────────────────────────
    rag_chunks: list[dict]
    episodic_context: list[dict]

    # ── Proactive loop (orchestrator only) ────────────────────────────────────
    last_trigger_check: Optional[str]
