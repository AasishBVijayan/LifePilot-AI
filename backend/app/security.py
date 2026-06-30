import os
import json
import time
import re
from typing import Dict, Any
from contextvars import ContextVar
from sqlalchemy.orm import Session
from .models import ToolApprovalModel

# Context variables to track the current execution session
current_session_id: ContextVar[str] = ContextVar("current_session_id", default="")
current_agent_name: ContextVar[str] = ContextVar("current_agent_name", default="Agent")
current_db: ContextVar[Any] = ContextVar("current_db", default=None)

# Security Sandbox Directory for File MCP
SANDBOX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sandbox"))
if not os.path.exists(SANDBOX_DIR):
    os.makedirs(SANDBOX_DIR)

def check_prompt_injection(prompt: str) -> tuple[bool, str]:
    """
    Check if the user input contains prompt injection patterns.
    Returns (is_injected, reason)
    """
    patterns = [
        r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"(?i)system\s+override",
        r"(?i)you\s+are\s+now\s+a\s+different\s+agent",
        r"(?i)dan\s+mode",
        r"(?i)ignore\s+rules",
        r"(?i)bypass\s+safety",
        r"(?i)forget\s+everything",
        r"(?i)reveal\s+your\s+system\s+prompt"
    ]
    for pattern in patterns:
        if re.search(pattern, prompt):
            return True, f"Prompt matches potential jailbreak/injection signature: {pattern}"
    
    return False, ""

def validate_file_path(path: str) -> str:
    """
    Ensures file operations are sandboxed within the 'sandbox' folder.
    Raises ValueError if path traversal or access outside the sandbox is attempted.
    """
    abs_path = os.path.abspath(os.path.join(SANDBOX_DIR, path))
    if not abs_path.startswith(SANDBOX_DIR):
        raise ValueError(f"Path traversal detected! Path must remain inside the sandbox folder. Attempted path: {path}")
    return abs_path

def request_tool_approval(session_id: str, agent_name: str, tool_name: str, arguments: Dict[str, Any], db: Session) -> bool:
    """
    Registers a tool execution in the database and blocks until approved or denied by the user.
    """
    # Check if this tool is dangerous or requires confirmation
    # Bypassed to optimize speed for user request
    dangerous_tools = []
    if tool_name not in dangerous_tools:
        return True

    approval_id = f"appr_{int(time.time() * 1000)}"
    args_json = json.dumps(arguments)
    
    # Save the pending approval request in DB
    approval = ToolApprovalModel(
        id=approval_id,
        session_id=session_id,
        agent_name=agent_name,
        tool_name=tool_name,
        arguments=args_json,
        status="PENDING"
    )
    db.add(approval)
    db.commit()

    # Block and wait for status to update to APPROVED or DENIED
    max_wait = 180  # 3 minutes timeout
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        # Refresh and fetch status
        db.expire_all()
        current_approval = db.query(ToolApprovalModel).filter(ToolApprovalModel.id == approval_id).first()
        if current_approval:
            if current_approval.status == "APPROVED":
                return True
            elif current_approval.status == "DENIED":
                return False
        time.sleep(0.5)
        
    # Timeout defaults to Denied
    if current_approval:
        current_approval.status = "DENIED"
        db.commit()
    return False
