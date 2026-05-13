"""Tool framework for claw agents.

Philosophy:
    * A Tool is a small async Python callable with a JSON-schema describing its
      arguments. Tools are collected into a registry; each agent picks which
      tools it wants to expose to its LLM.
    * The same Tool objects are used both by the LLM (via tool-calling) and by
      the REST API, so the frontend and the agents share functionality.

Nothing here depends on a specific LLM provider.
"""
from .base import Tool, ToolError, ToolRegistry  # noqa: F401
from .registry import build_default_registry  # noqa: F401
