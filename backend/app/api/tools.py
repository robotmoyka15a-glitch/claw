"""REST endpoint listing all registered tools.

The Agent Config UI renders this to let the user pick which tools an agent
is allowed to call.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.tools import build_default_registry


router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools():
    reg = build_default_registry()
    return reg.describe()
