import os
import json
import sys
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from duckduckgo_search import DDGS

# Initialize FastMCP Server
mcp = FastMCP("LifePilot MCP Server")

# Sandbox directory setup
SANDBOX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sandbox"))
if not os.path.exists(SANDBOX_DIR):
    os.makedirs(SANDBOX_DIR)

def validate_path(filename: str) -> str:
    """Ensures paths are sandboxed within the sandbox/ directory."""
    abs_path = os.path.abspath(os.path.join(SANDBOX_DIR, filename))
    if not abs_path.startswith(SANDBOX_DIR):
        raise ValueError(f"Path traversal detected! Path must remain inside the sandbox folder. Attempted: {filename}")
    return abs_path

@mcp.tool()
def mcp_web_search(query: str) -> str:
    """
    Search the web for live career trends, certifications, online courses, and salary data.
    
    Args:
        query: The search query text.
    """
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(f"Title: {r.get('title')}\nLink: {r.get('href')}\nSnippet: {r.get('body')}\n")
        return "\n---\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Web search failed: {str(e)}"

@mcp.tool()
def mcp_write_file(filename: str, content: str) -> str:
    """
    Write or update a file containing a career roadmap or analysis inside the sandboxed directory.
    
    Args:
        filename: Relative name or path of the file to write.
        content: The full text content to write.
    """
    try:
        safe_path = validate_path(filename)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Success: Content written to '{filename}' inside the sandbox."
    except Exception as e:
        return f"Error writing file: {str(e)}"

@mcp.tool()
def mcp_create_calendar_milestone(title: str, start_date: str, end_date: str) -> str:
    """
    Schedule a milestone or career roadmap timeline phase in the virtual calendar.
    
    Args:
        title: Title of the timeline phase or milestone.
        start_date: Start date (YYYY-MM-DD format).
        end_date: End date (YYYY-MM-DD format).
    """
    calendar_path = os.path.join(SANDBOX_DIR, "calendar.json")
    try:
        events = []
        if os.path.exists(calendar_path):
            try:
                with open(calendar_path, "r", encoding="utf-8") as f:
                    events = json.load(f)
            except json.JSONDecodeError:
                pass
        
        events.append({
            "title": title,
            "start_date": start_date,
            "end_date": end_date
        })
        
        with open(calendar_path, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
            
        return f"Success: Scheduled event '{title}' from {start_date} to {end_date} in calendar.json."
    except Exception as e:
        return f"Error writing calendar milestone: {str(e)}"

@mcp.tool()
def mcp_calculate_finance_roi(initial_investment: float, annual_growth_rate: float, years: int, monthly_contribution: float = 0.0) -> str:
    """
    Calculate educational and career investment return metrics (ROI).
    
    Args:
        initial_investment: The starting capital (e.g. ₹50,000).
        annual_growth_rate: Estimated annual return in decimals (e.g. 0.08 for 8%).
        years: Investment period in years.
        monthly_contribution: Optional monthly savings added.
    """
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
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error in ROI calculations: {str(e)}"

if __name__ == "__main__":
    # Start FastMCP server in stdio transport mode
    mcp.run()
