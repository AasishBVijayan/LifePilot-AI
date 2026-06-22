import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    query = Column(Text, nullable=False)
    status = Column(String, default="PENDING")  # PENDING, RUNNING, AWAITING_APPROVAL, COMPLETED, FAILED
    final_report = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    traces = relationship("AgentTraceModel", back_populates="session", cascade="all, delete-orphan")
    approvals = relationship("ToolApprovalModel", back_populates="session", cascade="all, delete-orphan")

class AgentTraceModel(Base):
    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    agent_name = Column(String, nullable=False)
    step_type = Column(String, nullable=False)  # REASONING, COMMUNICATION, TOOL_CALL, TOOL_RESPONSE, DEBATE, STATUS
    content = Column(Text, nullable=False)
    meta_data = Column(Text, nullable=True)  # JSON formatted meta arguments
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("SessionModel", back_populates="traces")

class ToolApprovalModel(Base):
    __tablename__ = "tool_approvals"

    id = Column(String, primary_key=True)  # Unique approval ID
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    agent_name = Column(String, nullable=False)
    tool_name = Column(String, nullable=False)
    arguments = Column(Text, nullable=False)  # JSON string
    status = Column(String, default="PENDING")  # PENDING, APPROVED, DENIED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("SessionModel", back_populates="approvals")

class DynamicAgentModel(Base):
    __tablename__ = "dynamic_agents"

    name = Column(String, primary_key=True)
    description = Column(Text, nullable=False)
    system_prompt = Column(Text, nullable=False)
    tools_config = Column(Text, nullable=False)  # JSON list of allowed tools
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
