"""Entry point: python -m agent.main

Starts:
  1. AsyncSqliteSaver checkpointer
  2. LangGraph compiled graph
  3. Teams polling loop (skipped if Teams env vars are absent — dev mode)
"""
import asyncio
import logging
import os
import sys

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from . import episodic
from .graph import build_graph
from .state import AgentState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

CHECKPOINTS_DB = os.path.join(
    os.environ.get("AGENT_DATA_DIR", "/opt/qnoe-agent/memory"),
    "checkpoints.db",
)

# Whether Teams credentials are configured
_TEAMS_CONFIGURED = all(
    os.environ.get(v)
    for v in ("TEAMS_TENANT_ID", "TEAMS_CLIENT_ID", "TEAMS_USERNAME", "TEAMS_PASSWORD")
)


async def handle_message(
    graph,
    conversation_id: str,
    thread_id: str | None,
    user_id: str,
    text: str,
    agent_id: str = "orchestrator",
) -> str:
    """Process one incoming Teams message; return the reply text."""
    session_id = thread_id or conversation_id
    config = {"configurable": {"thread_id": session_id}}

    # Load existing state snapshot to carry forward conversation history
    snapshot = await graph.aget_state(config)
    existing_messages: list = []
    existing_turns: int = 0
    existing_summary = None
    if snapshot and snapshot.values:
        stored_agent_id = snapshot.values.get("agent_id", "orchestrator")
        existing_messages = snapshot.values.get("messages", [])
        existing_turns = snapshot.values.get("turns_since_summary", 0)
        existing_summary = snapshot.values.get("conversation_summary")
    else:
        stored_agent_id = agent_id

    # Handle sub-team selection — only when currently set to orchestrator
    if stored_agent_id == "orchestrator":
        selected = _parse_subteam_selection(text)
        if selected:
            stored_agent_id = selected

    user_msg = {
        "role": "user",
        "content": text,
        "timestamp": _now(),
        "user_id": user_id,
    }

    input_state: dict = {
        "agent_id": stored_agent_id,
        "session_id": session_id,
        "active_user": user_id,
        "active_channel": conversation_id,
        "messages": existing_messages + [user_msg],
        "task_history": [],
        "rag_chunks": [],
        "episodic_context": [],
        "turns_since_summary": existing_turns,
        "conversation_summary": existing_summary,
    }

    result = await graph.ainvoke(input_state, config)

    messages = result.get("messages", [])
    if not messages:
        return "I encountered an error and could not generate a response."

    # Return the last assistant message
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            return msg["content"]

    return "I encountered an error and could not generate a response."


def _parse_subteam_selection(text: str) -> str | None:
    """Map a user's disambiguation reply to an agent_id."""
    t = text.strip().lower()
    mapping = {
        "qed": "qed",
        "superconductivity": "superconductivity",
        "supercon": "superconductivity",
        "photocurrent": "photocurrent",
        "photo": "photocurrent",
        "qtm": "qtm",
        "qsim": "qsim",
        "xchiral": "xchiral",
        "full lab": "orchestrator",
        "unsure": "orchestrator",
    }
    for key, agent in mapping.items():
        if key in t:
            return agent
    return None


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def run_dev_repl(graph) -> None:
    """Interactive REPL for local testing without Teams credentials."""
    logger.info("Starting dev REPL (no Teams credentials configured)")
    session_id = "dev-session-001"
    user_id = "dev-user"
    agent_id = "orchestrator"

    print("\n=== QNOE Agent dev REPL ===")
    print("Type your message. Commands: /switch, /help, /new, quit\n")

    loop = asyncio.get_running_loop()
    while True:
        try:
            text = await loop.run_in_executor(None, lambda: input("You: "))
            text = text.strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not text:
            continue
        if text.lower() in ("quit", "exit"):
            break

        reply = await handle_message(
            graph, session_id, None, user_id, text, agent_id=agent_id
        )
        print(f"\nAgent: {reply}\n")

        # Persist sub-team selection from disambiguation
        selected = _parse_subteam_selection(text)
        if selected:
            agent_id = selected


async def main() -> None:
    # Add file handler — logs go to AGENT_LOG_DIR (stdout is always on via basicConfig)
    log_dir = os.environ.get("AGENT_LOG_DIR", "/opt/qnoe-agent/logs")
    log_path = os.path.join(log_dir, "agent.log")
    try:
        logging.getLogger().addHandler(logging.FileHandler(log_path))
    except (PermissionError, OSError):
        logger.warning("Cannot write log file at %s", log_path)

    episodic.ensure_schema()

    async with AsyncSqliteSaver.from_conn_string(CHECKPOINTS_DB) as checkpointer:
        graph = build_graph(checkpointer)
        logger.info("LangGraph compiled, checkpointer at %s", CHECKPOINTS_DB)

        if _TEAMS_CONFIGURED:
            from .teams import TeamsConnector
            connector = TeamsConnector()

            async def on_message(conv_id, thread_id, user_id, text):
                return await handle_message(graph, conv_id, thread_id, user_id, text)

            connector.on_message = on_message
            logger.info("Starting Teams polling loop")
            await connector.run()
        else:
            logger.warning(
                "Teams env vars not set — running in dev REPL mode. "
                "Set TEAMS_TENANT_ID, TEAMS_CLIENT_ID, TEAMS_USERNAME, TEAMS_PASSWORD "
                "to enable Teams integration."
            )
            await run_dev_repl(graph)


if __name__ == "__main__":
    asyncio.run(main())
