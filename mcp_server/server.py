
"""
FastMCP Server for AI Productivity Agent
FINAL VERSION — Fixed Imports + Production Ready
"""

from __future__ import annotations

import sys
from pathlib import Path

# ✅ Ensure project root is in PYTHONPATH
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from typing import Optional, List, Dict, Any
import json
import requests
import logging
from fastmcp import FastMCP

# ✅ FIXED IMPORTS (NO circular import)
from mcp_server.storage import StorageManager
from mcp_server.utils import generate_id, format_timestamp


# ─────────────────────────────
# INIT
# ─────────────────────────────

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("productivity-server")
storage = StorageManager()


# ─────────────────────────────
# LOGGING HELPERS
# ─────────────────────────────

def log_tool_call(tool_name: str, args: Dict[str, Any], result: Dict[str, Any]):
    """Log tool calls for debugging."""
    logger.info(f"TOOL CALL: {tool_name} with args: {list(args.keys())}")
    if result.get("success"):
        logger.info(f"TOOL SUCCESS: {tool_name}")
    else:
        logger.error(f"TOOL ERROR: {tool_name} - {result.get('error', 'Unknown error')}")


# ─────────────────────────────
# HELPERS
# ─────────────────────────────

def success(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"success": True, "data": data}


def failure(error: str) -> Dict[str, Any]:
    return {"success": False, "error": error}


def validate_priority(priority: str) -> bool:
    return priority in ["low", "medium", "high"]


# ─────────────────────────────
# NOTES
# ─────────────────────────────

@mcp.tool()
def add_note(title: str, content: str, tags: Optional[List[str]] = None) -> Dict[str, Any]:
    """Create a new note with title, content, and optional tags.
    
    Args:
        title: Note title (required, max 200 characters)
        content: Note content (required, max 10,000 characters)  
        tags: Optional list of tags (max 20 tags, 50 characters each)
    
    Returns:
        Dict with note_id, message, and created note data
    """
    
    args = {"title": title, "content": content, "tags": tags}
    
    # Enhanced validation
    if not title or not title.strip():
        result = failure("Title is required and cannot be empty")
        log_tool_call("add_note", args, result)
        return result
    
    if not content or not content.strip():
        result = failure("Content is required and cannot be empty")
        log_tool_call("add_note", args, result)
        return result
    
    if len(title) > 200:
        result = failure("Title too long (max 200 characters)")
        log_tool_call("add_note", args, result)
        return result

    if len(content) > 10000:
        result = failure("Content too long (max 10,000 characters)")
        log_tool_call("add_note", args, result)
        return result

    if tags:
        if not isinstance(tags, list):
            result = failure("Tags must be a list of strings")
            log_tool_call("add_note", args, result)
            return result
        if len(tags) > 20:
            result = failure("Too many tags (max 20)")
            log_tool_call("add_note", args, result)
            return result
        # Validate each tag
        for tag in tags:
            if not isinstance(tag, str):
                result = failure("All tags must be strings")
                log_tool_call("add_note", args, result)
                return result
        tags = [str(t)[:50] for t in tags]

    note_id = generate_id()
    now = format_timestamp()

    note = {
        "id": note_id,
        "title": title.strip(),
        "content": content.strip(),
        "tags": tags or [],
        "created_at": now,
        "updated_at": now,
    }

    try:
        storage.save_note(note)
        result = success({"note_id": note_id, "message": f"Note '{title}' created", "note": note})
        log_tool_call("add_note", args, result)
        return result
    except Exception as e:
        result = failure(f"Failed to save note: {str(e)}")
        log_tool_call("add_note", args, result)
        return result


@mcp.tool()
def list_notes() -> Dict[str, Any]:
    """Retrieve all saved notes."""
    try:
        notes = storage.get_all_notes()
        return success({"total_notes": len(notes), "notes": list(notes.values())})
    except Exception as e:
        return failure(str(e))


@mcp.tool()
def search_notes(query: str) -> Dict[str, Any]:
    """Search notes by keyword."""
    if not query:
        return failure("Query is required")

    try:
        results = storage.search_notes(query)
        return success({"query": query, "total_results": len(results), "results": results})
    except Exception as e:
        return failure(str(e))


# ─────────────────────────────
# TASKS
# ─────────────────────────────

@mcp.tool()
def add_task(task: str, priority: str = "medium", due_date: Optional[str] = None) -> Dict[str, Any]:
    """Create a new task with priority and optional due date.
    
    Args:
        task: Task description (required, max 500 characters)
        priority: Priority level (low, medium, high - default: medium)
        due_date: Optional due date string (e.g., "tomorrow", "2024-12-25")
    
    Returns:
        Dict with task_id, message, and created task data
    """
    
    args = {"task": task, "priority": priority, "due_date": due_date}
    
    # Enhanced validation
    if not task or not task.strip():
        result = failure("Task description is required and cannot be empty")
        log_tool_call("add_task", args, result)
        return result
    
    if len(task) > 500:
        result = failure("Task description too long (max 500 characters)")
        log_tool_call("add_task", args, result)
        return result
    
    if not validate_priority(priority):
        result = failure("Priority must be: low, medium, or high")
        log_tool_call("add_task", args, result)
        return result
    
    if due_date and len(str(due_date)) > 100:
        result = failure("Due date too long (max 100 characters)")
        log_tool_call("add_task", args, result)
        return result
    
    task_id = generate_id()
    now = format_timestamp()

    task_obj = {
        "id": task_id,
        "task": task.strip(),
        "priority": priority,
        "due_date": due_date,
        "completed": False,
        "created_at": now,
        "completed_at": None,
    }

    try:
        storage.save_task(task_obj)
        return success({"task_id": task_id, "message": "Task created", "task": task_obj})
    except Exception as e:
        return failure(str(e))


@mcp.tool()
def complete_task(task_id: str) -> Dict[str, Any]:
    """Mark a task as completed."""

    try:
        task = storage.get_task(task_id)

        if not task:
            return failure("Task not found")

        if task["completed"]:
            return failure("Task already completed")

        task["completed"] = True
        task["completed_at"] = format_timestamp()

        storage.save_task(task)

        return success({"task_id": task_id, "message": "Task completed"})
    except Exception as e:
        return failure(str(e))


@mcp.tool()
def list_tasks() -> Dict[str, Any]:
    """Retrieve all tasks."""
    try:
        tasks = storage.get_all_tasks()
        return success({"total_tasks": len(tasks), "tasks": list(tasks.values())})
    except Exception as e:
        return failure(str(e))


# ─────────────────────────────
# SUMMARY (USES STORAGE HELPER)
# ─────────────────────────────

@mcp.tool()
def get_summary() -> Dict[str, Any]:
    """Return workspace summary."""
    try:
        stats = storage.get_stats()
        return success({"summary": stats})
    except Exception as e:
        return failure(str(e))


# ------------------------------
# WEB FETCHING
# ------------------------------

@mcp.tool()
def fetch_url(url: str) -> Dict[str, Any]:
    """Fetch content from a web URL."""
    
    print(f"[DEBUG] fetch_url called with URL: {url}")
    args = {"url": url}
    
    if not url:
        print("[DEBUG] URL validation failed: empty URL")
        result = failure("URL is required")
        log_tool_call("fetch_url", args, result)
        return result
    
    # Basic URL validation
    if not (url.startswith('http://') or url.startswith('https://')):
        print(f"[DEBUG] URL validation failed: {url}")
        result = failure("URL must start with http:// or https://")
        log_tool_call("fetch_url", args, result)
        return result
    
    try:
        print(f"[DEBUG] Attempting to fetch: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        print(f"[DEBUG] Response status: {response.status_code}")
        response.raise_for_status()
        
        # Limit content size to prevent token limit issues
        content = response.text
        if len(content) > 8000:
            content = content[:8000] + "\n\n[Content truncated due to size]"
        
        result = success({
            "url": url,
            "status_code": response.status_code,
            "content": content,
            "content_type": response.headers.get('content-type', 'unknown'),
            "content_length": len(content)
        })
        print(f"[DEBUG] Fetch successful, content length: {len(content)}")
        log_tool_call("fetch_url", args, result)
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"[DEBUG] RequestException: {e}")
        result = failure(f"Failed to fetch URL: {str(e)}")
        log_tool_call("fetch_url", args, result)
        return result
    except Exception as e:
        print(f"[DEBUG] Unexpected error: {e}")
        result = failure(f"Unexpected error: {str(e)}")
        log_tool_call("fetch_url", args, result)
        return result


# ─────────────────────────────
# BONUS: RESOURCES
# ─────────────────────────────

@mcp.resource("workspace://overview")
def workspace_overview():
    """Get complete workspace overview including notes and tasks."""
    try:
        notes = list(storage.get_all_notes().values())
        tasks = list(storage.get_all_tasks().values())
        stats = storage.get_stats()
        
        return {
            "stats": stats,
            "notes": notes,
            "tasks": tasks,
            "last_updated": format_timestamp()
        }
    except Exception as e:
        return {"error": str(e), "notes": [], "tasks": []}

@mcp.resource("workspace://notes")
def workspace_notes():
    """Get all notes for context."""
    try:
        notes = list(storage.get_all_notes().values())
        return {"notes": notes, "total": len(notes)}
    except Exception as e:
        return {"error": str(e), "notes": []}

@mcp.resource("workspace://tasks")
def workspace_tasks():
    """Get all tasks for context."""
    try:
        tasks = list(storage.get_all_tasks().values())
        return {"tasks": tasks, "total": len(tasks)}
    except Exception as e:
        return {"error": str(e), "tasks": []}


# ─────────────────────────────
# BONUS: PROMPTS
# ─────────────────────────────

@mcp.prompt("weekly_review")
def weekly_review_prompt() -> str:
    """Generate a comprehensive weekly review prompt with current workspace data."""
    try:
        notes = list(storage.get_all_notes().values())
        tasks = list(storage.get_all_tasks().values())
        stats = storage.get_stats()
        
        return f"""You are an expert AI productivity analyst conducting a weekly review.

WORKSPACE STATISTICS:
- Total Notes: {stats.get('total_notes', 0)}
- Total Tasks: {stats.get('total_tasks', 0)}
- Completed Tasks: {stats.get('completed_tasks', 0)}
- Pending Tasks: {stats.get('pending_tasks', 0)}

RECENT NOTES:
{json.dumps(notes[-5:], indent=2) if notes else "No notes found"}

CURRENT TASKS:
{json.dumps(tasks, indent=2) if tasks else "No tasks found"}

Please generate a comprehensive weekly review including:
1. **Overview**: Summary of productivity this week
2. **Achievements**: Completed tasks and key accomplishments
3. **Knowledge Gained**: Important insights from notes
4. **Pending Work**: Outstanding tasks and priorities
5. **Recommendations**: Action items for next week
6. **Productivity Score**: Rate overall productivity (1-10)

Be specific, actionable, and encouraging.
"""
    except Exception as e:
        return f"Error generating weekly review: {str(e)}"

@mcp.prompt("research_workflow")
def research_workflow_prompt() -> str:
    """Provide a structured research workflow template."""
    return """You are an AI research assistant. Follow this structured workflow:

1. **URL Validation**: Ensure the provided URL is accessible and relevant
2. **Content Fetching**: Use fetch_url to get the actual content
3. **Content Analysis**: Extract key information, insights, and important details
4. **Summary Creation**: Create a concise yet comprehensive summary
5. **Note Creation**: Save the research with appropriate tags and title

RESEARCH BEST PRACTICES:
- Always use fetch_url with the exact URL provided
- Never make up information or hallucinate content
- Extract the most valuable and relevant information
- Structure notes with clear titles and descriptive tags
- Include source attribution in the note content

If no URL is provided, ask the user for a specific URL to research.
"""

@mcp.prompt("task_management")
def task_management_prompt() -> str:
    """Provide task management best practices."""
    return """You are an AI task management assistant. Follow these principles:

TASK CREATION:
- Use clear, specific, and actionable language
- Set appropriate priorities (low, medium, high)
- Include realistic due dates when relevant
- Break down large tasks into smaller subtasks

TASK COMPLETION:
- Always use complete_task with the exact task_id
- Verify task completion before marking as done
- Provide confirmation when tasks are completed

PRODUCTIVITY TIPS:
- Focus on high-priority tasks first
- Set realistic deadlines
- Review and update tasks regularly
- Celebrate completed tasks to maintain motivation

Always ask for clarification if task descriptions are unclear.
"""


# ─────────────────────────────
# ENTRYPOINT
# ─────────────────────────────

if __name__ == "__main__":
    mcp.run()

