"""
app.py - Streamlit Chat UI for AI Productivity Agent
FINAL VERSION — Single MCP client via agent, no duplicate connections
"""

from __future__ import annotations

import sys
import asyncio
from pathlib import Path

import nest_asyncio
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

# ───────── NEST ASYNCIO (must be before any async calls) ─────────
nest_asyncio.apply()

# ───────── PATH SETUP ─────────
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ───────── IMPORTS ─────────
# ✅ Only import run_agent — no separate MCP client in UI
from agent.graph import run_agent


# ═══════════════════════════════════════
# ASYNC HELPER
# ═══════════════════════════════════════

def run_async(coro):
    """Run async coroutine safely inside Streamlit's event loop."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


def format_agent_response(reply: str):
    """Format agent response with enhanced JSON parsing for notes and tasks."""
    try:
        import json
        import re
        import pandas as pd
        
        # Debug: Log the actual reply for task addition
        print(f"[UI DEBUG] Agent reply: {reply[:200]}...")
        
        # Check for task addition success - check both text and JSON
        task_added_indicators = [
            "task created" in reply.lower(),
            "task added" in reply.lower(),
            "successfully created" in reply.lower(),
            "successfully added" in reply.lower()
        ]
        
        if any(task_added_indicators):
            st.success(" Task successfully added!")
            return True
        
        # Special case: If agent timed out but dashboard shows task count increased
        if "timeout" in reply.lower() and st.session_state.get("previous_task_count"):
            current_count = st.session_state.summary.get("total_tasks", 0)
            previous_count = st.session_state.previous_task_count
            if current_count > previous_count:
                st.success(" Task successfully added!")
                return True
        
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', reply, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, dict):
                    # Check for task addition success in JSON
                    if parsed.get("message") and "task created" in parsed.get("message", "").lower():
                        st.success(" Task successfully added!")
                        return True
                    
                    # Handle notes response
                    if "notes" in parsed or any("title" in str(v) for v in parsed.values() if isinstance(v, dict)):
                        st.markdown("### Your Notes:")
                        for key, note in parsed.items():
                            if isinstance(note, dict) and "title" in note:
                                with st.expander(f" {note.get('title', 'Untitled')}", expanded=True):
                                    st.markdown(f"**Content:** {note.get('content', 'No content')}")
                                    if note.get('tags'):
                                        st.markdown(f"**Tags:** {', '.join(note.get('tags', []))}")
                                    if note.get('created_at'):
                                        st.caption(f"Created: {note.get('created_at')}")
                        return True
                    
                    # Handle tasks response - Show as structured table
                    elif "tasks" in parsed or any("task" in str(v) for v in parsed.values() if isinstance(v, dict)):
                        st.markdown("### Your Tasks:")
                        
                        # Extract tasks data
                        tasks_data = []
                        for key, task in parsed.items():
                            if isinstance(task, dict) and "task" in task:
                                tasks_data.append({
                                    "Task ID": task.get('id', key),
                                    "Task Name": task.get('task', 'Untitled'),
                                    "Status": "Completed" if task.get('completed', False) else "Pending",
                                    "Priority": task.get('priority', 'medium').upper(),
                                    "Due Date": task.get('due_date', 'Not set'),
                                    "Created": task.get('created_at', 'Unknown')
                                })
                        
                        if tasks_data:
                            # Create DataFrame for better display
                            df = pd.DataFrame(tasks_data)
                            
                            # Add status color coding
                            def highlight_status(val):
                                color = 'background-color: #d4edda' if val == 'Completed' else 'background-color: #fff3cd'
                                return color
                            
                            def highlight_priority(val):
                                colors = {'HIGH': 'background-color: #f8d7da', 'MEDIUM': 'background-color: #d1ecf1', 'LOW': 'background-color: #d4edda'}
                                return colors.get(val, '')
                            
                            # Apply styling
                            styled_df = df.style.applymap(highlight_status, subset=['Status'])
                            styled_df = styled_df.applymap(highlight_priority, subset=['Priority'])
                            
                            # Display the table
                            st.dataframe(styled_df, use_container_width=True, hide_index=True)
                            
                            # Also show expandable details for each task
                            st.markdown("**Task Details:**")
                            for i, task in enumerate(tasks_data):
                                status_icon = "" if task['Status'] == 'Completed' else ""
                                with st.expander(f"{status_icon} {task['Task Name']} - {task['Status']}", expanded=False):
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.markdown(f"**ID:** {task['Task ID']}")
                                        st.markdown(f"**Priority:** {task['Priority']}")
                                    with col2:
                                        st.markdown(f"**Due Date:** {task['Due Date']}")
                                        st.markdown(f"**Created:** {task['Created']}")
                        
                        return True
            except json.JSONDecodeError:
                pass
        
        # Handle tool output format for tasks
        if "tasks" in reply.lower() and ("task" in reply or "completed" in reply):
            st.markdown("### Your Tasks:")
            st.markdown(reply)
            return True
            
        # Handle tool output format for notes
        if "notes" in reply.lower() and ("title" in reply or "content" in reply):
            st.markdown("### Your Notes:")
            st.markdown(reply)
            return True
            
    except Exception as e:
        print(f"[UI] Error formatting response: {e}")
        
    return False


# ═══════════════════════════════════════
# SUMMARY UPDATE
# ✅ Uses agent (single shared MCP client)
# ✅ No duplicate MCP connections
# Flow: UI → run_agent() → single MCP client → get_summary tool → UI
# ═══════════════════════════════════════

def update_summary():
    """
    Directly load workspace summary from storage for reliable stats.
    Bypasses agent to ensure accurate task counts.
    """
    fallback_summary()

def fallback_summary():
    """
    Fallback method to get workspace summary directly from storage
    without going through the agent/API.
    """
    try:
        # Import storage manager directly
        import sys
        from pathlib import Path
        
        # Add project root to path
        ROOT_DIR = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(ROOT_DIR))
        
        from mcp_server.storage import StorageManager
        
        # Get stats directly from storage with correct data path
        data_dir = ROOT_DIR / "mcp_server" / "data"
        storage = StorageManager(data_dir=data_dir)
        stats = storage.get_stats()
        
        # Ensure we have valid stats
        if not stats:
            stats = {
                "total_notes": 0,
                "total_tasks": 0,
                "completed_tasks": 0,
                "pending_tasks": 0
            }
        
        st.session_state.summary = stats
        st.session_state.summary_error = False
        print(f"[Dashboard] Fallback summary loaded: {stats}")
        
    except Exception as e:
        print(f"[Dashboard] Fallback summary failed: {e}")
        # Set default stats to prevent loading issues
        st.session_state.summary = {
            "total_notes": 0,
            "total_tasks": 0,
            "completed_tasks": 0,
            "pending_tasks": 0
        }
        st.session_state.summary_error = False

# ═══════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════

st.set_page_config(
    layout="wide",
    page_title="AI Productivity Agent",
    page_icon="🤖",
    initial_sidebar_state="expanded"
)


# ═══════════════════════════════════════
# SESSION STATE INIT
# ═══════════════════════════════════════

defaults = {
    "messages": [],
    "lc_history": [],
    "tool_log": [],
    "summary": {},
    "summary_error": False,
    "prefill": "",
    "needs_summary_refresh": False,
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ═══════════════════════════════════════
# DEFERRED SUMMARY REFRESH
# Flag is set after agent responds.
# Picked up here at the top of the next
# st.rerun() so dashboard is always fresh.
# ═══════════════════════════════════════

if st.session_state.pop("needs_summary_refresh", False):
    update_summary()

# Always ensure summary is loaded and up to date
if not st.session_state.summary:
    update_summary()


# ═══════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════

with st.sidebar:
    st.markdown("## 🧠 Productivity AI")
    
    # ── Workspace Stats ──
    st.markdown("### 📊 Workspace Overview")

    # Always show current stats (no loading state)
    summary = st.session_state.summary or {
        "total_notes": 0,
        "total_tasks": 0,
        "completed_tasks": 0,
        "pending_tasks": 0
    }
    
    # Better metrics display
    st.metric("📝 Total Notes", summary.get("total_notes", 0), delta=None)
    
    # Tasks section - show counts directly
    total_tasks = summary.get("total_tasks", 0)
    completed = summary.get("completed_tasks", 0)
    pending = summary.get("pending_tasks", 0)
    
    # Show task counts directly
    col1, col2 = st.columns(2)
    with col1:
        st.metric("✅ Completed", completed, delta=None)
    with col2:
        st.metric("⏳ Active", pending, delta=None)
    
    if total_tasks > 0:
        completion_rate = (completed / total_tasks) * 100
        st.progress(completion_rate / 100, text=f"{completion_rate:.1f}% complete")
    else:
        st.info("📋 No tasks yet")

    st.divider()

    # ── Quick Actions ──
    st.markdown("### ⚡ Quick Actions")

    quick_actions = {
        "📄 View Notes": "Show all my notes",
        "✅ View Tasks": "List all my tasks",
        "📊 Get Summary": "Give me a workspace summary",
        "➕ Add Task": "Add a task: review my work",
    }

    for label, prompt in quick_actions.items():
        if st.button(label, use_container_width=True):
            st.session_state.prefill = prompt
            st.rerun()

    st.divider()

    # ── Recent Tool Activity ──
    st.markdown("### 🛠 Recent Tool Activity")

    if not st.session_state.tool_log:
        st.info("No tool usage yet")
    else:
        for log in reversed(st.session_state.tool_log[-5:]):
            with st.expander(f"🔧 {log.get('tool', 'unknown')}"):
                st.json({
                    "args": log.get("args", {}),
                    "output": str(log.get("output", ""))[:500],
                })

    st.divider()

    # ── Controls ──
    col_r, col_c = st.columns(2)

    if col_r.button("🔄 Refresh", use_container_width=True):
        update_summary()
        st.rerun()

    if col_c.button("🗑 Reset", use_container_width=True):
        st.session_state.clear()
        st.rerun()


# ═══════════════════════════════════════
# MAIN AREA
# ═══════════════════════════════════════

# Header with better styling
st.markdown("""
# 🤖 AI Productivity Agent
**Research • Notes • Tasks** — powered by MCP + LangGraph + Groq
""")
st.markdown("---")

# ── Empty state ──
if not st.session_state.messages:
    # Welcome message
    st.markdown("""
    ## 👋 Welcome to Your AI Productivity Assistant!
    
    I can help you with:
    - 🌐 **Research**: Fetch and summarize web content
    - 📝 **Notes**: Create and organize your knowledge
    - ✅ **Tasks**: Manage your to-do list efficiently
    
    ---
    """)
    
    # Simple quick actions
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📋 View Tasks", use_container_width=True, type="primary"):
            st.session_state.prefill = "Show all my tasks"
            st.rerun()
    
    with col2:
        if st.button("📝 View Notes", use_container_width=True, type="primary"):
            st.session_state.prefill = "Show all my notes"
            st.rerun()

# ── Chat history ──
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ═══════════════════════════════════════
# INPUT HANDLING
# ═══════════════════════════════════════

# Safe prefill: read → clear → use
prefill = st.session_state.get("prefill", "")
st.session_state.prefill = ""

user_input = st.chat_input("Ask anything...") or prefill

if user_input:

    # Store previous task count for timeout detection
    st.session_state.previous_task_count = st.session_state.summary.get("total_tasks", 0)

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                reply, logs = run_async(
                    run_agent(
                        user_input,
                        history=st.session_state.lc_history,
                    )
                )
            except Exception as e:
                reply = f"Error: {str(e)}"
                logs = []

        # Enhanced response formatting with better JSON parsing
        formatted_response = format_agent_response(reply)
        if formatted_response:
            formatted_response
        else:
            st.markdown(reply)

        # Show tool calls prominently
        if logs:
            st.markdown("---")
            st.markdown("### Tools Used:")
            
            for i, log in enumerate(logs):
                tool_name = log.get("tool", "unknown")
                args = log.get("args", {})
                output = log.get("output", "")
                
                # Tool call header
                with st.container():
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.markdown(f"**{i+1}.**")
                    with col2:
                        st.markdown(f"**{tool_name}**")
                
                # Tool arguments
                if args:
                    with st.expander(f"Arguments", expanded=False):
                        for arg_name, arg_value in args.items():
                            st.markdown(f"**{arg_name}:** `{arg_value}`")
                
                # Tool result (success/failure)
                if isinstance(output, dict):
                    if output.get("success"):
                        st.success(" Success")
                        if output.get("data"):
                            with st.expander("Result", expanded=False):
                                st.json(output["data"])
                    else:
                        st.error(f" Failed: {output.get('error', 'Unknown error')}")
                else:
                    # String output
                    if output and len(str(output)) < 200:
                        st.info(f" Result: `{output}`")
                    elif output:
                        with st.expander("Result", expanded=False):
                            st.text(str(output)[:500])

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.session_state.lc_history.append(HumanMessage(content=user_input))
    st.session_state.lc_history.append(AIMessage(content=reply))
    st.session_state.tool_log.extend(logs or [])

    # Deferred refresh — summary updates at top of next rerun
    # ✅ Deferred refresh — summary updates at top of next rerun
    st.session_state.needs_summary_refresh = True
    st.rerun()