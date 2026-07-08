"""Async LLM client pointing at vLLM (OpenAI-compatible).

Inside OpenShell sandbox:  VLLM_BASE_URL = https://inference.local/v1  (default)
Outside sandbox (dev/test): VLLM_BASE_URL = http://localhost:8000/v1
"""
import asyncio
import logging
import os

from openai import AsyncOpenAI

from .tools import TOOL_DEFINITIONS, execute_tool_call

logger = logging.getLogger(__name__)

VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "https://inference.local/v1")
VLLM_MODEL = os.environ.get("VLLM_MODEL", "/opt/qnoe-agent/models/hermes-3-70b-awq")

MAX_TOOL_ROUNDS = 5  # safety cap on tool-call loops

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=VLLM_BASE_URL, api_key="not-needed")
    return _client


async def chat(
    messages: list[dict],
    *,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    timeout: float = 120.0,
) -> str:
    response = await get_client().chat.completions.create(
        model=VLLM_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    if not response.choices:
        raise RuntimeError("vLLM returned empty choices list")
    return response.choices[0].message.content or ""


async def chat_with_tools(
    messages: list[dict],
    *,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    timeout: float = 120.0,
) -> tuple[str, list[dict]]:
    """Chat with tool-calling support.

    Returns (final_text, tool_results) where tool_results is a list of
    {"tool": name, "input": args, "output": result} dicts for logging.
    """
    tool_log: list[dict] = []
    loop = asyncio.get_running_loop()

    for _round in range(MAX_TOOL_ROUNDS):
        response = await get_client().chat.completions.create(
            model=VLLM_MODEL,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
        if not response.choices:
            raise RuntimeError("vLLM returned empty choices list")

        choice = response.choices[0]

        # If no tool calls, return the text response
        if not choice.message.tool_calls:
            return choice.message.content or "", tool_log

        # Process tool calls
        # Add the assistant message with tool_calls to conversation
        messages.append(choice.message.model_dump())

        for tc in choice.message.tool_calls:
            name = tc.function.name
            args = tc.function.arguments
            logger.info("Tool call: %s(%s)", name, args[:200] if isinstance(args, str) else args)

            result = await loop.run_in_executor(None, execute_tool_call, name, args)

            # Truncate very long results
            if len(result) > 40_000:
                result = result[:40_000] + "\n... (truncated)"

            tool_log.append({"tool": name, "input": args, "output": result[:500]})

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    # Hit max rounds — do a final call without tools
    logger.warning("Hit max tool rounds (%d), forcing final response", MAX_TOOL_ROUNDS)
    return await chat(messages, max_tokens=max_tokens, temperature=temperature, timeout=timeout), tool_log
