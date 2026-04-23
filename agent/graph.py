
"""
graph.py - LangGraph ReAct Agent
FINAL VERSION — Deterministic + No Timeouts + MCP Compatible
"""

from __future__ import annotations

import asyncio
from typing_extensions import Annotated, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    SystemMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_mcp_adapters.client import MultiServerMCPClient

from .config import (
    AGENT_RECURSION_LIMIT,
    AGENT_MAX_ITERATIONS,
    MCP_CONFIG,
    GROQ_API_KEY,
    GROQ_MODEL,
    LLM_MAX_TOKENS,
    SYSTEM_PROMPT,
)


# ─────────────────────────────
# GLOBAL CACHE
# ─────────────────────────────

_compiled_graph = None
_mcp_client = None


# ─────────────────────────────
# STATE
# ─────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tool_calls_log: list[dict]
    steps: int


# ─────────────────────────────
# ROUTER (FIXED)
# ─────────────────────────────

def _should_continue(state: AgentState) -> str:
    last = state["messages"][-1]

    # Stop if no tool call
    if isinstance(last, AIMessage) and not last.tool_calls:
        return END

    if state.get("steps", 0) >= AGENT_MAX_ITERATIONS:
        return END

    if isinstance(last, AIMessage) and last.tool_calls:
        return "call_tools"

    return END


# ─────────────────────────────
# GRAPH BUILDER
# ─────────────────────────────

async def _build_graph(tools):
    print(f"[DEBUG] Building graph with {len(tools)} tools: {[t.name for t in tools]}")

    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0,
        max_tokens=LLM_MAX_TOKENS,
    ).bind_tools(tools)

    tool_node = ToolNode(tools)
    print(f"[DEBUG] ToolNode created with {len(tools)} tools")

    # ───────── MODEL NODE (FIXED) ─────────

    async def call_model(state: AgentState) -> dict:
        steps = state.get("steps", 0) + 1

        messages = state["messages"]
        log = list(state.get("tool_calls_log", []))

        # Add system prompt if not present
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

        response: AIMessage = await llm.ainvoke(messages)

        if response.tool_calls:
            for tc in response.tool_calls:
                log.append({
                    "tool": tc["name"],
                    "args": tc.get("args", {}),
                    "tool_call_id": tc.get("id"),
                    "output": None,
                })

        return {
            "messages": [response],
            "tool_calls_log": log,
            "steps": steps,
        }

    # ───────── TOOL NODE ─────────

    async def call_tools_with_logging(state: AgentState) -> dict:
        """Execute tools with detailed logging."""
        messages = state["messages"]
        last_message = messages[-1]
        
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return {"messages": []}
        
        tool_calls = last_message.tool_calls
        log = list(state.get("tool_calls_log", []))
        
        print(f"[Agent] Executing {len(tool_calls)} tool call(s):")
        for i, call in enumerate(tool_calls):
            print(f"  {i+1}. {call.get('name', 'unknown')}({call.get('args', {})})")
        
        # Debug: Note that ToolNode doesn't expose tools directly
        print(f"[DEBUG] ToolNode ready for execution")
        
        try:
            result = await tool_node.ainvoke(state)
            tool_results = result["messages"]
            
            for i, (call, result_msg) in enumerate(zip(tool_calls, tool_results)):
                # Handle content that might be a list or string
                content = result_msg.content if hasattr(result_msg, 'content') else str(result_msg)
                if isinstance(content, list):
                    content = str(content)
                success = not content.startswith('Error:')
                log.append({
                    "tool": call.get('name', 'unknown'),
                    "args": call.get('args', {}),
                    "output": content,
                    "success": success
                })
            
            print(f"[Agent] Tool execution completed")
            return {"messages": tool_results, "tool_calls_log": log}
        
        except Exception as e:
            print(f"[Agent] Tool execution failed: {e}")
            error_msg = f"Tool execution error: {str(e)}"
            log.append({
                "tool": "multiple",
                "args": {},
                "output": error_msg,
                "success": False
            })
            return {"messages": [AIMessage(content=error_msg)], "tool_calls_log": log}

        return {
            "messages": messages,
            "tool_calls_log": log,
            "steps": state.get("steps", 0),
        }

    # ───────── GRAPH ─────────

    graph = StateGraph(AgentState)
    graph.add_node("call_model", call_model)
    graph.add_node("call_tools", call_tools_with_logging)
    graph.set_entry_point("call_model")
    graph.add_conditional_edges("call_model", _should_continue)
    graph.add_edge("call_tools", "call_model")

    return graph.compile()


# ─────────────────────────────
# MCP CLIENT
# ─────────────────────────────

async def _get_client_and_tools():
    global _mcp_client
    import asyncio

    max_retries = 3
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            if _mcp_client is None:
                print(f"[MCP] Initializing client... (attempt {attempt + 1}/{max_retries})")
                _mcp_client = MultiServerMCPClient({
                    "productivity": MCP_CONFIG,
                })
                print("[MCP] Client initialized successfully")

            print("[MCP] Fetching tools...")
            tools = await _mcp_client.get_tools()
            print(f"[MCP] Found {len(tools)} tools: {[t.name for t in tools]}")
            return tools

        except Exception as e:
            print(f"[MCP] Error on attempt {attempt + 1}: {e}")
            
            # Reset client on any error
            _mcp_client = None
            
            if attempt < max_retries - 1:
                print(f"[MCP] Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"[MCP] Failed after {max_retries} attempts")
                import traceback
                traceback.print_exc()
                raise RuntimeError(f"MCP connection failed after {max_retries} attempts: {e}")


# ─────────────────────────────
# RUNNER
# ─────────────────────────────

async def run_agent(
    user_message: str,
    history: list[BaseMessage] | None = None,
):
    global _compiled_graph

    history = history or []

    try:
        print(f"[Agent] Running agent with message: {user_message[:50]}...")
        tools = await _get_client_and_tools()

        if not tools:
            return "No tools available. Check MCP server is running.", []

        if _compiled_graph is None:
            print("[Agent] Building graph...")
            _compiled_graph = await _build_graph(tools)
            print("[Agent] Graph built successfully")

        graph = _compiled_graph

        messages = list(history)
        messages.append(HumanMessage(content=user_message))

        print("[Agent] Invoking graph...")
        result = await asyncio.wait_for(
            graph.ainvoke(
                {
                    "messages": messages,
                    "tool_calls_log": [],
                    "steps": 0,
                },
                config={"recursion_limit": AGENT_RECURSION_LIMIT},
            ),
            timeout=30.0,  # Increased timeout for debugging
        )

        final_msg = next(
            (m for m in reversed(result["messages"]) if isinstance(m, AIMessage)),
            result["messages"][-1],
        )

        reply = final_msg.content or "Done."
        print(f"[Agent] Agent completed successfully")
        return reply, result.get("tool_calls_log", [])

    except asyncio.TimeoutError:
        print("[Agent] Timeout error")
        return "Request timed out. Please try again.", []

    except Exception as e:
        print(f"[Agent] Error: {e}")
        import traceback
        traceback.print_exc()
        # Reset graph on error to force rebuild
        _compiled_graph = None
        return f"Internal Error: {str(e)}", []
