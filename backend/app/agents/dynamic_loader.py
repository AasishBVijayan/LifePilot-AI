import json
import os
from sqlalchemy.orm import Session
from google.adk import Agent
from ..models import DynamicAgentModel
from ..mcp.tools import web_search, read_file, write_file

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Map of tool names to actual functions for dynamic registration
TOOL_MAP = {
    "web_search": web_search,
    "read_file": read_file,
    "write_file": write_file
}

def load_dynamic_agents(db: Session) -> list[Agent]:
    """
    Loads all dynamic agents stored in the SQLite database and instantiates them as ADK Agents.
    """
    db_agents = db.query(DynamicAgentModel).all()
    agents = []
    
    for db_agent in db_agents:
        try:
            # Parse configured tools
            tool_names = json.loads(db_agent.tools_config)
            agent_tools = [TOOL_MAP[name] for name in tool_names if name in TOOL_MAP]
            
            new_agent = Agent(
                name=db_agent.name,
                model=MODEL_NAME,
                description=db_agent.description,
                instruction=db_agent.system_prompt,
                tools=agent_tools
            )
            agents.append(new_agent)
        except Exception as e:
            print(f"Error loading dynamic agent '{db_agent.name}': {str(e)}")
            
    return agents
