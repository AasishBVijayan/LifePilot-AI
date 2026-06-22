import os
import json
import logging
from sqlalchemy.orm import Session
from google import genai
from .models import DynamicAgentModel

logger = logging.getLogger("lifepilot.builder")

# Target directory for dynamic agent files
DYNAMIC_AGENTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "agents", "dynamic"))
if not os.path.exists(DYNAMIC_AGENTS_DIR):
    os.makedirs(DYNAMIC_AGENTS_DIR)

def build_and_register_agent(user_prompt: str, db: Session) -> dict:
    """
    Calls Gemini to generate the complete code and configuration for a custom agent,
    saves the assets to disk, and registers the agent in the database.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not configured.")
        
    client = genai.Client(api_key=api_key)
    
    # Prompt instruction asking for structured JSON output
    system_instruction = (
        "You are an AI developer agent builder. Generate a complete custom agent package based on the user's request. "
        "Your output must be a valid JSON object matching the following keys:\n"
        "1. 'name': A unique PascalCase name for the agent (letters only, e.g., 'StartupAdvisorAgent').\n"
        "2. 'description': A concise description of the agent's purpose.\n"
        "3. 'system_prompt': A highly detailed system instruction for the agent's role.\n"
        "4. 'tools': A JSON list containing sub-selection of allowed tool names. Choose only from: ['web_search', 'read_file', 'write_file'].\n"
        "5. 'test_code': A complete, runnable Python unittest script checking that the agent is properly instantiated.\n"
        "6. 'deployment_config': A complete Dockerfile configuration to deploy this agent as a standalone service.\n\n"
        "Return ONLY the raw JSON block without markdown formatting or code fences."
    )
    
    prompt = f"User Request: 'Create an agent that: {user_prompt}'"
    
    try:
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "response_mime_type": "application/json"
            }
        )
        
        # Parse output JSON
        data = json.loads(response.text)
        
        agent_name = data.get("name", "CustomAgent").strip().replace(" ", "")
        agent_desc = data.get("description", "A custom generated agent.")
        agent_system = data.get("system_prompt", "You are a helpful assistant.")
        agent_tools = data.get("tools", ["web_search"])
        agent_test = data.get("test_code", "")
        agent_docker = data.get("deployment_config", "")
        
        # Create folder for agent
        agent_folder = os.path.join(DYNAMIC_AGENTS_DIR, agent_name)
        if not os.path.exists(agent_folder):
            os.makedirs(agent_folder)
            
        # Write files to folder
        with open(os.path.join(agent_folder, "config.json"), "w", encoding="utf-8") as f:
            json.dump({
                "name": agent_name,
                "description": agent_desc,
                "tools": agent_tools
            }, f, indent=2)
            
        with open(os.path.join(agent_folder, "system_prompt.txt"), "w", encoding="utf-8") as f:
            f.write(agent_system)
            
        with open(os.path.join(agent_folder, "test_agent.py"), "w", encoding="utf-8") as f:
            f.write(agent_test)
            
        with open(os.path.join(agent_folder, "Dockerfile"), "w", encoding="utf-8") as f:
            f.write(agent_docker)
            
        # Save / Register to database
        db_agent = db.query(DynamicAgentModel).filter(DynamicAgentModel.name == agent_name).first()
        if db_agent:
            # Overwrite if exists
            db_agent.description = agent_desc
            db_agent.system_prompt = agent_system
            db_agent.tools_config = json.dumps(agent_tools)
        else:
            db_agent = DynamicAgentModel(
                name=agent_name,
                description=agent_desc,
                system_prompt=agent_system,
                tools_config=json.dumps(agent_tools)
            )
            db.add(db_agent)
            
        db.commit()
        
        return {
            "success": True,
            "name": agent_name,
            "description": agent_desc,
            "tools": agent_tools,
            "folder_path": agent_folder
        }
        
    except Exception as e:
        logger.error(f"Error creating custom agent: {str(e)}")
        raise e
