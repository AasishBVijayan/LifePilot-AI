import os
import json
from typing import Dict, Any, List
from duckduckgo_search import DDGS
from ..security import (
    current_session_id, current_agent_name, current_db,
    validate_file_path, request_tool_approval, SANDBOX_DIR
)
from ..models import AgentTraceModel

def _log_tool_trace(step_type: str, content: str, meta: dict = None):
    session_id = current_session_id.get()
    agent_name = current_agent_name.get()
    db = current_db.get()
    if session_id and db:
        trace = AgentTraceModel(
            session_id=session_id,
            agent_name=agent_name,
            step_type=step_type,
            content=content,
            meta_data=json.dumps(meta) if meta else None
        )
        db.add(trace)
        db.commit()

# --- WEB MCP TOOL ---
def web_search(query: str) -> str:
    """
    Search the web for real-time market trends, career salaries, courses, and educational trends.
    
    Args:
        query (str): The search query text.
    """
    agent = current_agent_name.get()
    _log_tool_trace("TOOL_CALL", f"Invoking Web Search: '{query}'", {"query": query})
    
    # We do not block web search for approvals, to keep experience fluid, but we log the call
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(f"Title: {r.get('title')}\nLink: {r.get('href')}\nSnippet: {r.get('body')}\n")
        
        output = "\n---\n".join(results) if results else "No results found."
        _log_tool_trace("TOOL_RESPONSE", f"Web Search returned {len(results)} snippets.")
        return output
    except Exception as e:
        error_msg = f"Web Search failed due to network or rate limits: {str(e)}. (Fallback to knowledge database)"
        _log_tool_trace("TOOL_RESPONSE", error_msg)
        return error_msg

# --- FILE MCP TOOLS ---
def read_file(filename: str) -> str:
    """
    Read the contents of a file inside the sandboxed user directory.
    
    Args:
        filename (str): The name or relative path of the file to read.
    """
    agent = current_agent_name.get()
    _log_tool_trace("TOOL_CALL", f"Invoking Read File: '{filename}'", {"filename": filename})
    
    try:
        safe_path = validate_file_path(filename)
        if not os.path.exists(safe_path):
            res = f"File '{filename}' does not exist."
            _log_tool_trace("TOOL_RESPONSE", res)
            return res
        
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
        _log_tool_trace("TOOL_RESPONSE", f"Read {len(content)} characters from file.")
        return content
    except Exception as e:
        res = f"Error reading file: {str(e)}"
        _log_tool_trace("TOOL_RESPONSE", res)
        return res

def write_file(filename: str, content: str) -> str:
    """
    Write specific content to a file inside the sandboxed user directory.
    Requires user permission approval.
    
    Args:
        filename (str): The name or relative path of the file.
        content (str): The text content to write.
    """
    agent = current_agent_name.get()
    _log_tool_trace("TOOL_CALL", f"Requesting Write File: '{filename}'", {"filename": filename, "content_preview": content[:100]})
    
    session_id = current_session_id.get()
    db = current_db.get()
    
    # Human-in-the-loop security check
    approved = request_tool_approval(session_id, agent, "write_file", {"filename": filename, "content": content}, db)
    if not approved:
        res = "Permission Denied: User rejected writing to file."
        _log_tool_trace("TOOL_RESPONSE", res)
        return res
        
    try:
        safe_path = validate_file_path(filename)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        res = f"Success: Content written to '{filename}'."
        _log_tool_trace("TOOL_RESPONSE", res)
        return res
    except Exception as e:
        res = f"Error writing file: {str(e)}"
        _log_tool_trace("TOOL_RESPONSE", res)
        return res

def list_files() -> str:
    """
    List all files inside the sandbox directory.
    """
    _log_tool_trace("TOOL_CALL", "Invoking List Files", {})
    try:
        files = os.listdir(SANDBOX_DIR)
        res = f"Sandbox files: {', '.join(files)}" if files else "Sandbox directory is empty."
        _log_tool_trace("TOOL_RESPONSE", res)
        return res
    except Exception as e:
        res = f"Error listing files: {str(e)}"
        _log_tool_trace("TOOL_RESPONSE", res)
        return res

# --- CALENDAR MCP TOOLS ---
def create_calendar_event(title: str, start_date: str, end_date: str, description: str) -> str:
    """
    Schedule a milestone or career roadmap event in the user's virtual calendar.
    Requires user permission approval.
    
    Args:
        title (str): Title of the event or milestone.
        start_date (str): Start date/time (YYYY-MM-DD format).
        end_date (str): End date/time (YYYY-MM-DD format).
        description (str): Description or tasks for this milestone.
    """
    agent = current_agent_name.get()
    args = {"title": title, "start_date": start_date, "end_date": end_date, "description": description}
    _log_tool_trace("TOOL_CALL", f"Requesting Create Calendar Event: '{title}'", args)
    
    session_id = current_session_id.get()
    db = current_db.get()
    
    # Human-in-the-loop security check
    approved = request_tool_approval(session_id, agent, "create_calendar_event", args, db)
    if not approved:
        res = "Permission Denied: User rejected calendar event creation."
        _log_tool_trace("TOOL_RESPONSE", res)
        return res

    # Store simulated calendar file inside sandbox
    calendar_path = os.path.join(SANDBOX_DIR, "calendar.json")
    try:
        events = []
        if os.path.exists(calendar_path):
            with open(calendar_path, "r") as f:
                events = json.load(f)
        
        events.append(args)
        with open(calendar_path, "w") as f:
            json.dump(events, f, indent=2)
            
        res = f"Success: Scheduled event '{title}' from {start_date} to {end_date}."
        _log_tool_trace("TOOL_RESPONSE", res)
        return res
    except Exception as e:
        res = f"Error writing to virtual calendar: {str(e)}"
        _log_tool_trace("TOOL_RESPONSE", res)
        return res

# --- FINANCE MCP TOOLS ---
def calculate_roi(initial_investment: float, annual_growth_rate: float, years: int, monthly_contribution: float = 0.0) -> str:
    """
    Calculate career/educational Return on Investment (ROI) and future value of savings.
    
    Args:
        initial_investment (float): Initial amount (e.g. ₹50,000).
        annual_growth_rate (float): Growth rate in decimals (e.g. 0.08 for 8%).
        years (int): Investment duration.
        monthly_contribution (float): Optional monthly savings added.
    """
    _log_tool_trace("TOOL_CALL", "Invoking ROI Calculator", {
        "initial": initial_investment, "rate": annual_growth_rate, "years": years, "monthly": monthly_contribution
    })
    
    try:
        fv = initial_investment
        total_contributions = 0
        r_monthly = annual_growth_rate / 12
        months = years * 12
        
        for _ in range(months):
            fv = fv * (1 + r_monthly) + monthly_contribution
            total_contributions += monthly_contribution
            
        total_invested = initial_investment + total_contributions
        gains = fv - total_invested
        roi = (gains / total_invested) * 100 if total_invested > 0 else 0
        
        res = {
            "Total Invested": f"₹{total_invested:,.2f}",
            "Future Value": f"₹{fv:,.2f}",
            "Net Gains": f"₹{gains:,.2f}",
            "ROI Percentage": f"{roi:.2f}%"
        }
        
        output = json.dumps(res, indent=2)
        _log_tool_trace("TOOL_RESPONSE", f"ROI calculated: {output}")
        return output
    except Exception as e:
        res = f"Error calculating ROI: {str(e)}"
        _log_tool_trace("TOOL_RESPONSE", res)
        return res
