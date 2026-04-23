
"""
agent.py - Entry point wrapper for the AI Productivity Agent.

This module provides:
- arun_agent(): async execution
- run_agent_sync(): Streamlit-safe sync wrapper
- chat(): simple interface (returns only reply)

Handles:
- async execution
- event loop conflicts (Streamlit/Jupyter)
- tool logging
- conversation history management
"""

from __future__ import annotations

import asyncio
import traceback
from typing import List, Tuple, TypedDict

import nest_asyncio
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


# ─────────────────────────────────────────────
# SAFE IMPORT (WORKS BOTH AS MODULE + SCRIPT)
# ─────────────────────────────────────────────

from agent.graph import run_agent

# ─────────────────────────────────────────────
# TOOL LOG TYPE
# ─────────────────────────────────────────────

class ToolLog(TypedDict):
    tool: str
    args: dict
    output: str


# ─────────────────────────────────────────────
# CORE ASYNC FUNCTION
# ─────────────────────────────────────────────

async def arun_agent(
    user_input: str,
    history: List[BaseMessage] | None = None,
) -> Tuple[str, List[ToolLog], List[BaseMessage]]:
    """
    Async wrapper around run_agent()

    Returns:
    - reply (str)
    - tool_logs (List[ToolLog])
    - updated_history (List[BaseMessage])
    """

    history = history or []

    try:
        reply, tool_logs = await run_agent(user_input, history)

        # Ensure safe outputs
        reply = reply or "⚠️ No response generated."
        tool_logs = tool_logs or []

    except Exception as e:
        # Capture full traceback for debugging
        reply = f"❌ Error: {str(e)}"
        tool_logs = [{
            "tool": "error",
            "args": {},
            "output": traceback.format_exc()
        }]

    # NOTE: We intentionally store even error replies in history
    updated_history = history + [
        HumanMessage(content=user_input),
        AIMessage(content=reply),
    ]

    return reply, tool_logs, updated_history


# ─────────────────────────────────────────────
# SYNC WRAPPER (STREAMLIT SAFE)
# ─────────────────────────────────────────────

def run_agent_sync(
    user_input: str,
    history: List[BaseMessage] | None = None,
) -> Tuple[str, List[ToolLog], List[BaseMessage]]:
    """
    Runs agent in a synchronous context (Streamlit/Jupyter safe).
    Handles event loop conflicts gracefully.
    """

    try:
        return asyncio.run(arun_agent(user_input, history))

    except RuntimeError:
        # Event loop already running → fix with nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(arun_agent(user_input, history))


# ─────────────────────────────────────────────
# SIMPLE CHAT HELPER
# ─────────────────────────────────────────────

def chat(
    user_input: str,
    history: List[BaseMessage] | None = None,
) -> str:
    """
    Simple helper for quick usage.

    NOTE:
    - Returns ONLY reply
    - Discards tool logs and history updates
    """

    reply, _, _ = run_agent_sync(user_input, history)
    return reply


# ─────────────────────────────────────────────
# CLI TESTING (FOR DEMO / DEBUGGING)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 AI Productivity Agent (CLI Mode)")
    print("Type 'exit' to quit.\n")

    history: List[BaseMessage] = []

    while True:
        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        reply, logs, history = run_agent_sync(user_input, history)

        print("\nAssistant:", reply)

        if logs:
            print("\n🔧 Tools used:")
            for log in logs:
                print(f" - {log['tool']}({log.get('args', {})})")

        print("\n" + "-" * 50 + "\n")

