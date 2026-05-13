"""SQLAlchemy ORM models for agent persistence.

Tables:
  agents          — agent definitions
  agent_messages  — chat history
  scheduled_tasks — autonomous scheduled / event-driven tasks
  task_runs       — execution log for scheduled tasks
"""
from __future__ import annotations

import time

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


# ── Agents ────────────────────────────────────────────────────────────────────

class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    preset: Mapped[str] = mapped_column(String(40))
    desk: Mapped[str] = mapped_column(String(40))
    color: Mapped[str] = mapped_column(String(10))
    llm_provider: Mapped[str] = mapped_column(String(40), default="ollama")
    llm_model: Mapped[str] = mapped_column(String(120), default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    allowed_tools: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[float] = mapped_column(Float, default=lambda: time.time())

    messages: Mapped[list["AgentMessage"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan",
    )
    tasks: Mapped[list["ScheduledTask"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan",
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    ts: Mapped[float] = mapped_column(Float, default=lambda: time.time())

    agent: Mapped[Agent] = relationship(back_populates="messages")


# ── Autonomous tasks ──────────────────────────────────────────────────────────

class ScheduledTask(Base):
    """A task that runs autonomously on a schedule or when triggered by an event.

    trigger_type:
        "cron"    — cron expression in `trigger_value` (e.g. "*/15 * * * *")
        "interval"— seconds as integer string (e.g. "300")
        "event"   — event name in `trigger_value`
                     ("cpu_high", "vk_message", "tg_message", "process_new")
        "manual"  — only run when explicitly requested

    objective: natural-language description of what the agent should do.
    """
    __tablename__ = "scheduled_tasks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    objective: Mapped[str] = mapped_column(Text)
    trigger_type: Mapped[str] = mapped_column(String(20))   # cron|interval|event|manual
    trigger_value: Mapped[str] = mapped_column(String(120), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_iterations: Mapped[int] = mapped_column(Integer, default=6)
    created_at: Mapped[float] = mapped_column(Float, default=lambda: time.time())
    last_run_at: Mapped[float] = mapped_column(Float, default=0.0)
    next_run_at: Mapped[float] = mapped_column(Float, default=0.0)

    agent: Mapped[Agent] = relationship(back_populates="tasks")
    runs: Mapped[list["TaskRun"]] = relationship(
        back_populates="task", cascade="all, delete-orphan",
    )


class TaskRun(Base):
    """Execution log entry for a ScheduledTask."""
    __tablename__ = "task_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("scheduled_tasks.id", ondelete="CASCADE"), index=True
    )
    started_at: Mapped[float] = mapped_column(Float, default=lambda: time.time())
    finished_at: Mapped[float] = mapped_column(Float, default=0.0)
    trigger: Mapped[str] = mapped_column(String(40), default="scheduler")
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|ok|error
    summary: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")

    task: Mapped[ScheduledTask] = relationship(back_populates="runs")
