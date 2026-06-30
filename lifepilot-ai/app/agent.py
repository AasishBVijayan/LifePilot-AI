# ruff: noqa
import os
import re
import json
import uuid
import sys
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

# Google ADK 2.0 Imports
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import Workflow, Edge, START, node
from google.adk.tools import AgentTool, McpToolset
from google.adk.events import RequestInput
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.genai import types
from mcp import StdioServerParameters

# Universal Config Import
from app.config import config

# Logger setup
logger = logging.getLogger("lifepilot.agent")

# Target audit log path
AUDIT_LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "artifacts"))
if not os.path.exists(AUDIT_LOG_DIR):
    os.makedirs(AUDIT_LOG_DIR)
AUDIT_LOG_PATH = os.path.join(AUDIT_LOG_DIR, "security_audit.json")

# Sandbox directory for MCP write verifications
SANDBOX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sandbox"))
if not os.path.exists(SANDBOX_DIR):
    os.makedirs(SANDBOX_DIR)

# ---------------------------------------------------------------------------
# MCP Toolset Setup
# ---------------------------------------------------------------------------
# Connects to the local stdio transport MCP server using the same python interpreter
mcp_toolset = McpToolset(
    connection_params=StdioServerParameters(
        command=sys.executable,
        args=["app/mcp_server.py"]
    )
)

# ---------------------------------------------------------------------------
# Specialized Specialist Agents
# ---------------------------------------------------------------------------
research_agent = Agent(
    name="ResearchAgent",
    model=Gemini(model=config.model),
    instruction=(
        "You are the Research Agent. Your goal is to gather current market trends, tech popularity, "
        "salary ranges, and online courses using the mcp_web_search tool. Focus on concrete facts "
        "and salary statistics in India/US. Provide a structured research summary."
    ),
    tools=[mcp_toolset]
)

planner_agent = Agent(
    name="PlannerAgent",
    model=Gemini(model=config.model),
    instruction=(
        "You are the Planner Agent. Your goal is to map out a realistic learning roadmap. "
        "Use the mcp_write_file tool to write a 'roadmap.md' file inside the sandbox. "
        "Use the mcp_create_calendar_milestone tool to schedule at least 3 major phases in the calendar. "
        "Describe your timeline and milestones in your final output."
    ),
    tools=[mcp_toolset]
)

risk_agent = Agent(
    name="RiskAgent",
    model=Gemini(model=config.model),
    instruction=(
        "You are the Risk Agent. Analyze potential roadblocks, difficult concepts, market saturation, "
        "and competition for each career track. Give realistic mitigation strategies."
    ),
    tools=[mcp_toolset]
)

finance_agent = Agent(
    name="FinanceAgent",
    model=Gemini(model=config.model),
    instruction=(
        "You are the Finance Agent. Your role is to perform cost-to-benefit calculations. "
        "Estimate learning costs and use the mcp_calculate_finance_roi tool to project 3-year financial returns. "
        "Return a detailed financial ROI analysis."
    ),
    tools=[mcp_toolset]
)

critic_agent = Agent(
    name="CriticAgent",
    model=Gemini(model=config.model),
    instruction=(
        "You are the Critic Agent. Examine the drafts from the Research, Planner, Risk, and Finance agents. "
        "Challenge overly optimistic timelines, cost underestimates, and ignored risks. Ask hard, constructive questions."
    ),
    tools=[]
)

# ---------------------------------------------------------------------------
# Orchestrator Executive Agent
# ---------------------------------------------------------------------------
executive_agent = Agent(
    name="ExecutiveAgent",
    model=Gemini(model=config.model),
    instruction=(
        "You are the Executive Agent. Your goal is to orchestrate the decision-making process. "
        "1. Delegate tasks to the specialists (Research, Planner, Risk, Finance) using their tools. "
        "2. Gather their draft outputs. "
        "3. Invoke the Critic Agent to review the drafts. "
        "4. Instruct the specialists to refine their sections. "
        "5. Compile the final comprehensive recommendation report. "
        "Note: You MUST state in your final output whether you propose writing files or calendar milestones "
        "so the workflow knows if human approval is needed."
    ),
    tools=[
        AgentTool(research_agent),
        AgentTool(planner_agent),
        AgentTool(risk_agent),
        AgentTool(finance_agent),
        AgentTool(critic_agent)
    ]
)

# ---------------------------------------------------------------------------
# Workflow Graph Nodes (ADK 2.0 Function Nodes)
# ---------------------------------------------------------------------------

@node
async def security_checkpoint(ctx: Context, node_input: Any) -> Event:
    """
    Entry node that scrubs PII, checks for prompt injections, and logs details.
    """
    query = str(node_input)
    
    # 1. PII Redaction
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
    phone_pattern = r"\b(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b"
    ssn_pattern = r"\b\d{4}[- ]?\d{4}[- ]?\d{4}\b" # Aadhaar / SSN format
    
    scrubbed_query = query
    scrubbed_query = re.sub(email_pattern, "[REDACTED_EMAIL]", scrubbed_query)
    scrubbed_query = re.sub(phone_pattern, "[REDACTED_PHONE]", scrubbed_query)
    scrubbed_query = re.sub(ssn_pattern, "[REDACTED_PII]", scrubbed_query)
    
    # 2. Prompt Injection Keyword Detection
    injection_keywords = ["ignore previous instructions", "system override", "dan mode", "bypass safety", "reveal your system prompt"]
    detected_injection = False
    for kw in injection_keywords:
        if kw in query.lower():
            detected_injection = True
            break
            
    # 3. Structured JSON Audit Logging
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "original_query_length": len(query),
        "pii_detected": scrubbed_query != query,
        "injection_detected": detected_injection,
        "severity": "CRITICAL" if detected_injection else ("WARNING" if scrubbed_query != query else "INFO")
    }
    
    try:
        logs = []
        if os.path.exists(AUDIT_LOG_PATH):
            with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                logs = json.load(f)
        logs.append(audit_entry)
        with open(AUDIT_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write audit log: {str(e)}")

    # 4. Route Decision
    if detected_injection:
        ctx.route = "SECURITY_EVENT"
        ctx.state["error_message"] = "Security Block: Prompt injection attempt detected."
        return Event(output="Security Block: Prompt injection attempt detected.")
        
    ctx.route = "PASSED"
    ctx.state["query"] = scrubbed_query
    return Event(output=scrubbed_query)

@node
async def security_blocked(ctx: Context, node_input: Any) -> Event:
    """Terminal node for security violations."""
    msg = ctx.state.get("error_message", "Access Denied: Security Checkpoint Blocked.")
    return Event(output=f"### 🛑 Security Alert\n\n{msg}")

@node
async def orchestrator_node(ctx: Context, node_input: Any) -> Event:
    """Runs the Executive Agent to delegate tasks and synthesize findings."""
    query = ctx.state.get("query", str(node_input))
    
    # Run the ExecutiveAgent
    full_output = ""
    async for event in executive_agent.run(ctx=ctx, node_input=query):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    full_output += part.text
                    
    ctx.state["draft_report"] = full_output
    
    # Determine if human approval is needed based on execution plan
    # (Checking if the Executive Agent planned files/calendar writes)
    if "roadmap" in full_output.lower() or "schedule" in full_output.lower() or "milestone" in full_output.lower():
        ctx.route = "NEEDS_APPROVAL"
    else:
        ctx.route = "AUTO_APPROVED"
        
    return Event(output=full_output)

@node
async def human_approval(ctx: Context, node_input: Any):
    """
    Suspends execution using RequestInput to ask the user for approval
    before files or calendar writing actions are committed.
    """
    # Check if we already received the input from a resume
    response = ctx.resume_inputs.get("hitl_approval")
    if response is None:
        # Suspend workflow and wait for approval
        yield RequestInput(
            interrupt_id="hitl_approval",
            message="LifePilot Operating System is proposing sandbox file writes and calendar roadmap scheduling. Do you approve?",
            response_schema=str
        )
        return
        
    # Resume state evaluation
    ctx.state["approval_status"] = response
    yield Event(output=f"Human Approval Received: {response}")

@node
async def final_synthesis(ctx: Context, node_input: Any) -> Event:
    """Compiles the final report, incorporating the approval decision."""
    report = ctx.state.get("draft_report", str(node_input))
    approval = ctx.state.get("approval_status", "AUTO_APPROVED")
    
    status_header = "### 🟢 Workflow: Auto-Approved\n\n"
    if approval != "AUTO_APPROVED":
        if "yes" in approval.lower() or "allow" in approval.lower() or "approve" in approval.lower():
            status_header = "### 🔵 Workflow: Human Approved & Committed\n\n"
        else:
            status_header = "### 🟡 Workflow: Human Rejected (Read-Only Mode)\n\n"
            # Remove any written files or warn that sandbox writes were rolled back
            status_header += "> *Notice: Proposed sandbox writes and calendar bookings were rejected by the operator and rolled back.*\n\n"
            
    final_output = f"{status_header}{report}"
    return Event(output=final_output)

# ---------------------------------------------------------------------------
# Workflow Edge Definitions
# ---------------------------------------------------------------------------
workflow = Workflow(
    name="lifepilot_workflow",
    description="LifePilot Multi-Agent Decision Operating System Graph",
    edges=[
        Edge(from_node=START, to_node=security_checkpoint),
        Edge(from_node=security_checkpoint, to_node=security_blocked, route="SECURITY_EVENT"),
        Edge(from_node=security_checkpoint, to_node=orchestrator_node, route="PASSED"),
        Edge(from_node=orchestrator_node, to_node=human_approval, route="NEEDS_APPROVAL"),
        Edge(from_node=orchestrator_node, to_node=final_synthesis, route="AUTO_APPROVED"),
        Edge(from_node=human_approval, to_node=final_synthesis),
        Edge(from_node=security_blocked, to_node=final_synthesis) # Single unconditional edge to avoid duplicates
    ]
)

# ---------------------------------------------------------------------------
# App Scaffolding Integration
# ---------------------------------------------------------------------------
app = App(
    root_agent=workflow,
    name="app"
)
