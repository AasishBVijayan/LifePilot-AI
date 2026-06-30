import asyncio
import json
import logging
from sqlalchemy.orm import Session
from ..database import SessionLocal
from google.adk.runners import InMemoryRunner
from google.genai import types

from ..security import current_session_id, current_agent_name, current_db
from ..models import SessionModel, AgentTraceModel
from .executive import executive_agent
from .specialist import (
    research_agent, planner_agent
)

logger = logging.getLogger("lifepilot.orchestrator")

def save_status_trace(session_id: str, content: str, db: Session):
    """Utility to save execution status events visible in the Mission Control UI."""
    trace = AgentTraceModel(
        session_id=session_id,
        agent_name="System",
        step_type="STATUS",
        content=content
    )
    db.add(trace)
    db.commit()

async def run_agent(agent, prompt: str, session_id: str, db: Session, step_type: str = "REASONING", delay: float = 0.0) -> str:
    """Runs a single Google ADK agent asynchronously and stores its thoughts in the DB."""
    if delay > 0:
        await asyncio.sleep(delay)
        
    # Set context variables for tools/callbacks in this thread/task
    current_session_id.set(session_id)
    current_db.set(db)
    current_agent_name.set(agent.name)
    
    runner = InMemoryRunner(agent=agent)
    runner.auto_create_session = True
    new_message = types.UserContent(parts=[types.Part(text=prompt)])
    
    max_retries = 3
    for attempt in range(max_retries):
        full_response = ""
        try:
            # Run ADK agent asynchronously
            async for event in runner.run_async(
                user_id="user_pilot",
                session_id=session_id,
                new_message=new_message
            ):
                # Capture model responses/thoughts
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            full_response += part.text
                            
                            # Save each reasoning segment to the database
                            trace = AgentTraceModel(
                                session_id=session_id,
                                agent_name=agent.name,
                                step_type=step_type,
                                content=part.text
                            )
                            db.add(trace)
                            db.commit()
            return full_response
        except Exception as e:
            is_transient = any(term in str(e) for term in ["503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "rate limit"])
            if is_transient and attempt < max_retries - 1:
                is_rate_limit = any(term in str(e).upper() for term in ["429", "RESOURCE_EXHAUSTED", "RATE_LIMIT", "QUOTA"])
                if is_rate_limit:
                    wait_time = (attempt + 1) * 8
                else:
                    wait_time = (attempt + 1) * 3
                logger.warning(f"Transient API error in agent {agent.name}: {e}. Retrying in {wait_time}s (attempt {attempt+1}/{max_retries})...")
                save_status_trace(session_id, f"⚠️ Transient error in agent {agent.name}. Retrying in {wait_time}s...", db)
                await asyncio.sleep(wait_time)
                continue
                
            error_msg = f"Execution Error in agent {agent.name}: {str(e)}"
            logger.error(error_msg)
            trace = AgentTraceModel(
                session_id=session_id,
                agent_name=agent.name,
                step_type="STATUS",
                content=error_msg
            )
            db.add(trace)
            db.commit()
            raise e
        
    return full_response

async def run_lifepilot_workflow(session_id: str, query: str):
    """
    Main Multi-Agent Workflow:
    Executive Agent -> Parallel Specialists -> Debate Phase -> Consensus -> Final Recommendation
    """
    db = SessionLocal()
    # Initialize session state
    current_session_id.set(session_id)
    current_db.set(db)
    
    # 1. Update session status
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return
    session.status = "RUNNING"
    db.commit()
    
    save_status_trace(session_id, "🚀 Initializing LifePilot Decision Engine...", db)
    

    
    try:
        # 2. Parallel Execution of Specialists
        save_status_trace(session_id, "⚡ Activating specialist agents in parallel: Research, Planner...", db)
        
        research_prompt = (
            f"User Goal: {query}\n\n"
            f"Gather current market statistics, salary ranges, and job demand. "
            f"Return a structured research report."
        )
        
        planner_prompt = (
            f"User Goal: {query}\n\n"
            f"Create a step-by-step career timeline and learning roadmap. Use the write_file tool to save a "
            f"'roadmap.md' file inside the sandbox. "
            f"Return your roadmap details."
        )
        
        # Define specialist coroutines
        all_tasks = [
            run_agent(research_agent, research_prompt, session_id, db, delay=0.0),
            run_agent(planner_agent, planner_prompt, session_id, db, delay=0.5)
        ]
        
        # Execute in parallel
        results = await asyncio.gather(*all_tasks)
        
        research_rep = results[0]
        planner_rep = results[1]
        
        # 3. Final Synthesis (Executive Agent)
        save_status_trace(session_id, "✍️ Executive Agent is synthesizing final recommendation...", db)
        
        final_synthesis_prompt = (
            f"Consolidate everything into a definitive recommendation report for the user query: '{query}'\n\n"
            f"Inputs gathered from specialists:\n"
            f"- Research:\n{research_rep}\n"
            f"- Roadmap & Timeline:\n{planner_rep}\n"
            f"Structure the final report. Make a definitive career track recommendation. "
            f"Include a comparison matrix, timeline milestones, and study guidance. "
            f"Use professional formatting."
        )
        final_report = await run_agent(executive_agent, final_synthesis_prompt, session_id, db)
        
        # Save final report to DB
        session.status = "COMPLETED"
        session.final_report = final_report
        db.commit()
        
        save_status_trace(session_id, "✅ LifePilot decision analysis complete!", db)
        
    except Exception as e:
        session.status = "FAILED"
        db.commit()
        save_status_trace(session_id, f"❌ LifePilot workflow failed: {str(e)}", db)
        raise e
    finally:
        db.close()
