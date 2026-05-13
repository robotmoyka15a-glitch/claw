"""SQLAlchemy models for agent persistence."""
from __future__ import annotations

import time

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


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
    created_at: Mapped[float] = mapped_column(Float, default=lambda: time.time())

    messages: Mapped[list["AgentMessage"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # system|user|assistant
    content: Mapped[str] = mapped_column(Text)
    ts: Mapped[float] = mapped_column(Float, default=lambda: time.time())

    agent: Mapped[Agent] = relationship(back_populates="messages")
