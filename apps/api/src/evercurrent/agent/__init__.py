"""Tool-using agent layer.

`tools` registers the six tools the agent can call. `runner` drives the
multi-turn tool-use loop with bounded iterations. `streaming` serialises
runner events as SSE for the FastAPI endpoint.
"""

from evercurrent.agent.runner import AgentEvent, run_agent
from evercurrent.agent.tools import TOOL_SPECS, ToolContext, dispatch_tool

__all__ = ["TOOL_SPECS", "AgentEvent", "ToolContext", "dispatch_tool", "run_agent"]
