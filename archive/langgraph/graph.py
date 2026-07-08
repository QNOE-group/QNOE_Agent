"""LangGraph agent graph.

One compiled graph is shared across all sessions. Each invocation gets its
own thread_id (= Teams conversation_id or thread_id), which the SqliteSaver
checkpointer uses to isolate state.

Graph flow:
  START → route → [qtm_respond | photocurrent_respond | orchestrate | handle_command]
                                                                              → END
"""
import asyncio
import logging
from datetime import datetime, timezone

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .state import AgentState, Message
from .prompts import build_system_prompt, AGENT_COLLECTIONS
from .retrieval import retrieve
from .episodic import get_episodic_context, log_event
from . import llm as llm_mod

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS_PER_TURN = 10
SUMMARY_TURN_THRESHOLD = 60
SUMMARY_TOKEN_ESTIMATE = 14_000  # approx chars / 4


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_messages_to_openai(state: AgentState) -> list[dict]:
    """Convert AgentState messages to OpenAI chat format."""
    return [{"role": msg["role"], "content": msg["content"]} for msg in state["messages"]]


def _summary_block(state: AgentState) -> str:
    """Return conversation summary text, or empty string if none."""
    summary = state.get("conversation_summary")
    if not summary:
        return ""
    return f"\n\n[Earlier conversation summary]\n{summary}"


def _rag_context_block(chunks: list[dict], collections: list[str]) -> str:
    if not chunks:
        # Don't include failure message — let the model try tools first.
        # The model will report RAG failure on its own if tools also fail.
        return ""
    lines = ["[Retrieved context]"]
    for i, chunk in enumerate(chunks, 1):
        src = chunk.get("source") or chunk.get("repo") or chunk.get("collection", "")
        lines.append(f"[{i}] ({src})\n{chunk['text']}")
    return "\n\n".join(lines)


def _episodic_block(events: list[dict]) -> str:
    if not events:
        return ""
    lines = ["[Recent task history]"]
    for e in events:
        lines.append(
            f"- {e['timestamp'][:10]} {e['task_type']} {e.get('repo', '')} "
            f"→ {e['outcome']}: {e['summary']}"
        )
    return "\n".join(lines)


async def _summarise_if_needed(state: AgentState) -> AgentState:
    """Trim the message window and regenerate a summary if over threshold."""
    messages = state["messages"]
    total_chars = sum(len(m["content"]) for m in messages)
    if len(messages) < SUMMARY_TURN_THRESHOLD and total_chars < SUMMARY_TOKEN_ESTIMATE * 4:
        return state

    # Take oldest 30 turns, summarise them
    to_summarise = messages[:30]
    rest = messages[30:]

    conv_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in to_summarise
    )
    summary_prompt = [
        {
            "role": "user",
            "content": (
                "Summarise this conversation segment in ≤400 tokens, preserving: "
                "decisions made, tasks completed, key findings, any open questions.\n\n"
                + conv_text
            ),
        }
    ]
    new_summary = await llm_mod.chat(summary_prompt, max_tokens=400, temperature=0.1)

    existing = state.get("conversation_summary") or ""
    if existing:
        # Summary-of-summaries
        merge_prompt = [
            {
                "role": "user",
                "content": (
                    "Merge these two conversation summaries into one ≤800-token summary, "
                    "preserving all key decisions, tasks, findings, and open questions.\n\n"
                    f"EARLIER:\n{existing}\n\nNEWER:\n{new_summary}"
                ),
            }
        ]
        combined = await llm_mod.chat(merge_prompt, max_tokens=800, temperature=0.1)
    else:
        combined = new_summary

    state["messages"] = rest
    state["conversation_summary"] = combined
    state["turns_since_summary"] = 0
    return state


# ── Graph nodes ────────────────────────────────────────────────────────────────

def route(state: AgentState) -> str:
    """Conditional routing — returns the name of the next node."""
    messages = state.get("messages", [])
    if not messages:
        return "orchestrate"

    last = messages[-1]
    content = last.get("content", "").strip()

    # Command handling
    if content.startswith("/"):
        return "handle_command"

    # New session with no agent_id set → orchestrate to send disambiguation card
    agent_id = state.get("agent_id", "orchestrator")
    if agent_id == "orchestrator":
        return "orchestrate"
    if agent_id == "qtm":
        return "qtm_respond"
    if agent_id == "photocurrent":
        return "photocurrent_respond"
    # All other sub-agents default to orchestrator until Phase 2
    return "orchestrate"


async def _subagent_respond(state: AgentState, agent_id: str) -> dict:
    """Shared respond logic for sub-agents."""
    state = await _summarise_if_needed(state)

    if not state["messages"]:
        return {}
    user_msg = state["messages"][-1]["content"]
    collections = AGENT_COLLECTIONS.get(agent_id, ["group-wide"])

    # Retrieve RAG context
    chunks = await retrieve(user_msg, collections)

    # Retrieve episodic context
    episodic = await get_episodic_context(
        session_id=state["session_id"],
        user_id=state.get("active_user"),
        limit=5,
    )

    # Assemble messages for LLM
    system_prompt = build_system_prompt(agent_id)
    rag_block = _rag_context_block(chunks, collections)
    episodic_block = _episodic_block(episodic)

    context_suffix = "\n\n".join(filter(None, [
        _summary_block(state), episodic_block, rag_block,
    ]))
    if context_suffix:
        system_prompt = system_prompt + "\n\n" + context_suffix

    openai_messages = [{"role": "system", "content": system_prompt}]
    openai_messages += _state_messages_to_openai(state)

    response_text, tool_log = await llm_mod.chat_with_tools(openai_messages)
    if tool_log:
        logger.info("Tool calls this turn: %s", [t["tool"] for t in tool_log])

    new_msg: Message = {
        "role": "assistant",
        "content": response_text,
        "timestamp": _now(),
        "user_id": None,
    }

    # Log to episodic store
    await log_event(
        session_id=state["session_id"],
        agent_id=agent_id,
        task_type="qa",
        outcome="success",
        summary=response_text[:200],
        user_id=state.get("active_user"),
    )

    return {
        "agent_id": agent_id,
        "messages": state["messages"] + [new_msg],
        "conversation_summary": state.get("conversation_summary"),
        "turns_since_summary": state.get("turns_since_summary", 0) + 1,
        "rag_chunks": chunks,
        "episodic_context": episodic,
    }


async def qtm_respond(state: AgentState) -> dict:
    return await _subagent_respond(state, "qtm")


async def photocurrent_respond(state: AgentState) -> dict:
    return await _subagent_respond(state, "photocurrent")


async def orchestrate(state: AgentState) -> dict:
    """Orchestrator node — handles routing messages and cross-team queries."""
    messages = state.get("messages", [])

    # New session: no messages yet → disambiguation card text
    if not messages:
        card_text = (
            "Hello! I'm the QNOE lab agent.\n"
            "Which sub-team are you working with?\n\n"
            "Reply with: QED, Superconductivity, Photocurrent, QTM, QSIM, XCHIRAL, "
            "or 'full lab'."
        )
        new_msg: Message = {
            "role": "assistant",
            "content": card_text,
            "timestamp": _now(),
            "user_id": None,
        }
        return {"agent_id": "orchestrator", "messages": [new_msg]}

    return await _subagent_respond(state, "orchestrator")


async def handle_command(state: AgentState) -> dict:
    """Handle slash commands: /switch, /help, /new."""
    last = state["messages"][-1]["content"].strip()
    cmd = last.split()[0].lower()

    if cmd == "/switch":
        reply = (
            "Which sub-team would you like to switch to?\n\n"
            "Reply with: QED, Superconductivity, Photocurrent, QTM, QSIM, XCHIRAL, "
            "or 'full lab'."
        )
    elif cmd == "/help":
        agent_id = state.get("agent_id", "orchestrator")
        help_text = await llm_mod.chat([
            {"role": "system", "content": build_system_prompt(agent_id)},
            {"role": "user", "content": "/help"},
        ])
        reply = help_text
    elif cmd == "/new":
        reply = (
            f"Starting fresh. I still know your sub-team is "
            f"{state.get('agent_id', 'unset')} and have full access to group "
            f"knowledge — I just won't carry forward our previous conversation. "
            f"What are you working on?"
        )
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": reply,
                    "timestamp": _now(),
                    "user_id": None,
                }
            ],
            "conversation_summary": None,
            "turns_since_summary": 0,
            "current_task": None,
            "pending_approval": None,
        }
    else:
        reply = f"Unknown command: {cmd}. Available: /switch, /help, /new"

    new_msg: Message = {
        "role": "assistant",
        "content": reply,
        "timestamp": _now(),
        "user_id": None,
    }
    return {"messages": state["messages"] + [new_msg]}


# ── Graph construction ─────────────────────────────────────────────────────────

def build_graph(checkpointer):
    g = StateGraph(AgentState)

    g.add_node("qtm_respond", qtm_respond)
    g.add_node("photocurrent_respond", photocurrent_respond)
    g.add_node("orchestrate", orchestrate)
    g.add_node("handle_command", handle_command)

    g.add_conditional_edges(START, route, {
        "qtm_respond": "qtm_respond",
        "photocurrent_respond": "photocurrent_respond",
        "orchestrate": "orchestrate",
        "handle_command": "handle_command",
    })

    g.add_edge("qtm_respond", END)
    g.add_edge("photocurrent_respond", END)
    g.add_edge("orchestrate", END)
    g.add_edge("handle_command", END)

    return g.compile(checkpointer=checkpointer)
