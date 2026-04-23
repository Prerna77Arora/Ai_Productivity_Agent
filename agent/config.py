"""
config.py - Central configuration for the AI Productivity Agent
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv


# ─────────────────────────────────────────────
# PATH SETUP
# ─────────────────────────────────────────────

_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = _ROOT / ".env"


# ─────────────────────────────────────────────
# LOAD ENV
# ─────────────────────────────────────────────

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    print("[config] WARNING: .env file not found", file=sys.stderr)


# ─────────────────────────────────────────────
# ENV HELPER
# ─────────────────────────────────────────────

def _get_env(
    key: str,
    default: str | None = None,
    required: bool = False,
) -> str:
    """Fetch environment variables safely."""
    value = os.environ.get(key, default)

    if required and not value:
        raise ValueError(f"[config] Missing required env variable: {key}")

    if not required and value is None and default is None:
        print(f"[config] WARNING: {key} is not set", file=sys.stderr)

    return value or ""


# ─────────────────────────────────────────────
# API KEYS
# ─────────────────────────────────────────────

GROQ_API_KEY: str = _get_env("GROQ_API_KEY", required=True)


# ─────────────────────────────────────────────
# MODEL CONFIG
# ─────────────────────────────────────────────

GROQ_MODEL: str = _get_env("GROQ_MODEL", "llama-3.3-70b-versatile")
LLM_TEMPERATURE: float = float(_get_env("LLM_TEMPERATURE", "0"))
LLM_MAX_TOKENS: int = int(_get_env("LLM_MAX_TOKENS", "800"))


# ─────────────────────────────────────────────
# STORAGE CONFIG
# ─────────────────────────────────────────────

DATA_DIR: Path = _ROOT / "data"
NOTES_FILE: Path = DATA_DIR / "notes.json"
TASKS_FILE: Path = DATA_DIR / "tasks.json"

DATA_DIR.mkdir(exist_ok=True, parents=True)


# ─────────────────────────────────────────────
# MCP SERVER PATH
# ─────────────────────────────────────────────

MCP_SERVER_DIR: Path = _ROOT / "mcp_server"
MCP_SERVER_SCRIPT: Path = MCP_SERVER_DIR / "server.py"

if not MCP_SERVER_SCRIPT.exists():
    print(
        f"[config] WARNING: MCP server not found at {MCP_SERVER_SCRIPT}",
        file=sys.stderr,
    )


# ─────────────────────────────────────────────
# MCP SERVERS
# -----------------------------------------------------------------

# -----------------------------------------------------------------
# CRITICAL: Always inherit full os.environ in subprocess env.
# Without **os.environ the subprocess gets an EMPTY environment --
# no PATH, no PYTHONPATH, no venv -- and crashes immediately with
# "Connection closed". This was the root cause of BrokenResourceError.

MCP_CONFIG: Dict[str, Any] = {
    "command": sys.executable,
    "args": [str(_ROOT / "mcp_server" / "server.py")],
    "transport": "stdio",
    "env": {
        **os.environ,              # inherit full environment (PATH, venv, etc.)
        "PYTHONPATH": str(_ROOT),  # ensure mcp_server package is findable
    },
}


# ─────────────────────────────────────────────
# AGENT CONFIG
# ─────────────────────────────────────────────

AGENT_RECURSION_LIMIT: int = int(_get_env("AGENT_RECURSION_LIMIT", "25"))
AGENT_MAX_ITERATIONS: int = int(_get_env("AGENT_MAX_ITERATIONS", "10"))

if AGENT_MAX_ITERATIONS > AGENT_RECURSION_LIMIT:
    print("[config] WARNING: MAX_ITERATIONS > RECURSION_LIMIT", file=sys.stderr)


# ─────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are an AI Productivity Agent. Use MCP tools for all actions.

AVAILABLE TOOLS:
- add_note(title, content, tags): Create a new note
- list_notes(): Show all notes
- search_notes(query): Search notes by keyword
- add_task(task, priority, due_date): Create a task
- list_tasks(): Show all tasks
- complete_task(task_id): Mark task as complete
- get_summary(): Get workspace statistics
- fetch_url(url): Fetch content from a web URL

CRITICAL ANTI-HALLUCINATION RULES:
1. NEVER make up URLs, content, or data - only use what tools return
2. ALWAYS use fetch_url for research - never summarize without fetching
3. ONLY use URLs explicitly provided by the user
4. If no URL provided for research, ALWAYS ask for one
5. Verify tool execution before claiming results

CRITICAL JSON FORMATTING RULES:
1. ALWAYS generate valid JSON for tool calls - NO EXCEPTIONS
2. NEVER add extra spaces before closing tags: use </function> NOT </function> 
3. ALWAYS escape special characters: quotes, backslashes, forward slashes
4. NEVER include trailing spaces or malformed JSON
5. Double-check JSON syntax: {"key": "value"} format
6. If unsure, use simpler parameter values to avoid JSON errors

WORKFLOW RULES:
1. ALWAYS call tools directly - no explanations, no "I will..."
2. Return ONLY the tool result or a brief summary
3. For research: MUST have a URL to use fetch_url
4. Never make up URLs - only use URLs provided by the user
5. Keep responses concise and actionable
6. JSON VALIDATION: Ensure every tool call has perfect JSON syntax

RESEARCH WORKFLOW (STRICT):
- User provides URL -> fetch_url(url) -> analyze REAL content -> add_note(title, content, tags)
- No URL provided -> ask: "Please provide a specific URL to research"
- Never summarize without actual fetched content

TASK WORKFLOW:
- Default priority: medium
- Use list_tasks() to find task_id before completing
- Verify task exists before marking complete
- Handle special characters in task names properly (/, \, ", ')

ERROR HANDLING:
- If tool fails, show the exact error message
- If no data found, say "No data found"
- If unclear, ask for specific clarification
- Never assume tool results without verification

VERIFICATION REQUIREMENTS:
- Always confirm fetch_url succeeded before creating notes
- Always verify task_id exists before completing
- Always check tool success/failure status
- VALIDATE JSON: Ensure perfect syntax before any tool call

JSON EXAMPLES (CORRECT):
 {"url": "https://example.com"}
 {"task": "simple task", "priority": "medium"}
 {"title": "note title", "content": "note content"}

JSON EXAMPLES (INCORRECT):
 {"url": "https://example.com"} 
 {"task": "task/with/slashes"} 
 {"content": "unescaped "quotes"}
"""