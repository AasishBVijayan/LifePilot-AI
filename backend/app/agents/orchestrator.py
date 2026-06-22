import asyncio
import json
import logging
from sqlalchemy.orm import Session
from google.adk.runners import InMemoryRunner
from google.genai import types

from ..security import current_session_id, current_agent_name, current_db
from ..models import SessionModel, AgentTraceModel
from .executive import executive_agent
from .specialist import (
    research_agent, planner_agent, risk_agent, finance_agent, critic_agent
)
from .dynamic_loader import load_dynamic_agents

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

async def run_agent(agent, prompt: str, session_id: str, db: Session, step_type: str = "REASONING") -> str:
    """Runs a single Google ADK agent asynchronously and stores its thoughts in the DB."""
    # Set context variables for tools/callbacks in this thread/task
    current_session_id.set(session_id)
    current_db.set(db)
    current_agent_name.set(agent.name)
    
    runner = InMemoryRunner(agent=agent)
    new_message = types.UserContent(parts=[types.Part(text=prompt)])
    
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
    except Exception as e:
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

async def run_lifepilot_workflow(session_id: str, query: str, db: Session):
    """
    Main Multi-Agent Workflow:
    Executive Agent -> Parallel Specialists -> Debate Phase -> Consensus -> Final Recommendation
    """
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
    
    # Check if there are user dynamic agents to run
    dynamic_agents = load_dynamic_agents(db)
    if dynamic_agents:
        save_status_trace(session_id, f"Registered {len(dynamic_agents)} custom agent(s) for evaluation.", db)
    
    try:
        # 2. Executive Agent Decomposition
        save_status_trace(session_id, "📋 Executive Agent is deconstructing user query and planning specialist tasks...", db)
        exec_prompt = (
            f"The user is asking: '{query}'.\n"
            f"Deconstruct this decision query. Outline the key research, planner, risk, and finance tasks. "
            f"Assign objectives to each agent so they can build a structured comparison."
        )
        exec_decomposition = await run_agent(executive_agent, exec_prompt, session_id, db)
        
        # 3. Parallel Execution of Specialists
        save_status_trace(session_id, "⚡ Activating specialist agents in parallel: Research, Planner, Risk, Finance...", db)
        
        research_prompt = (
            f"User Goal: {query}\n\nDecomposition objectives:\n{exec_decomposition}\n\n"
            f"Gather current market statistics, tech stack popularity, and career opportunities using the web_search tool. "
            f"Return a structured research report."
        )
        
        planner_prompt = (
            f"User Goal: {query}\n\nDecomposition objectives:\n{exec_decomposition}\n\n"
            f"Create a step-by-step career timeline and learning roadmap. Use the write_file tool to save a "
            f"'roadmap.md' file inside the sandbox. Schedule 3 critical roadmap milestones using the create_calendar_event tool. "
            f"Return your roadmap details."
        )
        
        risk_prompt = (
            f"User Goal: {query}\n\nDecomposition objectives:\n{exec_decomposition}\n\n"
            f"Identify potential risks, failure points, technology shifts, and skill barriers for this track. "
            f"Return a structured risk assessment report."
        )
        
        finance_prompt = (
            f"User Goal: {query}\n\nDecomposition objectives:\n{exec_decomposition}\n\n"
            f"Analyze course costs, certification fees, living costs, and projected salary growth in India/US. "
            f"Use the calculate_roi tool to project 3-year financial returns. Return a detailed financial assessment."
        )
        
        # Define specialist coroutines
        tasks = [
            run_agent(research_agent, research_prompt, session_id, db),
            run_agent(planner_agent, planner_prompt, session_id, db),
            run_agent(risk_agent, risk_prompt, session_id, db),
            run_agent(finance_agent, finance_prompt, session_id, db)
        ]
        
        # Also run any user-generated custom agents in parallel
        dynamic_tasks = []
        for dyn_agent in dynamic_agents:
            dyn_prompt = (
                f"User Goal: {query}\n\nProvide your specialized analysis based on your background:\n"
                f"{dyn_agent.instruction}\nReturn your expert advisory report."
            )
            dynamic_tasks.append(run_agent(dyn_agent, dyn_prompt, session_id, db))
            
        all_tasks = tasks + dynamic_tasks
        
        # Execute in parallel
        results = await asyncio.gather(*all_tasks)
        
        research_rep = results[0]
        planner_rep = results[1]
        risk_rep = results[2]
        finance_rep = results[3]
        
        # Collect dynamic agent reports
        dyn_reports_str = ""
        for i, dyn_agent in enumerate(dynamic_agents):
            dyn_reports_str += f"\n- Custom Advisor ({dyn_agent.name}):\n{results[4 + i]}\n"
            
        # 4. Agent Debate Phase (Critic Agent)
        save_status_trace(session_id, "🗣️ Debate Phase: Critic Agent is evaluating draft reports and challenging assumptions...", db)
        
        critic_prompt = (
            f"User Goal: {query}\n\n"
            f"Specialist Draft Reports:\n"
            f"- Research:\n{research_rep}\n"
            f"- Roadmap:\n{planner_rep}\n"
            f"- Risks:\n{risk_rep}\n"
            f"- Finance:\n{finance_rep}\n"
            f"{dyn_reports_str}\n"
            f"Evaluate these reports. Point out gaps, unrealistic timelines, cost assumptions, or omitted risks. "
            f"Pose challenging questions for the specialists to refine."
        )
        critique = await run_agent(critic_agent, critic_prompt, session_id, db, step_type="DEBATE")
        
        # 5. Consensus Building (Specialists Refine)
        save_status_trace(session_id, "🤝 Consensus Phase: Specialists are refining their reports based on Critic challenges...", db)
        
        refinement_prompts = [
            run_agent(
                planner_agent, 
                f"Here is the Critic's evaluation of your roadmap:\n{critique}\n\n"
                f"Revise your roadmap to address these issues. Write the final roadmap to 'roadmap.md'. "
                f"Return the refined roadmap report.", 
                session_id, db
            ),
            run_agent(
                risk_agent, 
                f"Here is the Critic's critique of your risk assessment:\n{critique}\n\n"
                f"Revise and expand your risk assessment. Return the refined risk report.", 
                session_id, db
            ),
            run_agent(
                finance_agent, 
                f"Here is the Critic's critique of your financial analysis:\n{critique}\n\n"
                f"Update your salary projections or cost assessments. Return the refined financial report.", 
                session_id, db
            )
        ]
        
        refined_results = await asyncio.gather(*refinement_prompts)
        refined_planner = refined_results[0]
        refined_risk = refined_results[1]
        refined_finance = refined_results[2]
        
        # 6. Final Consensus Recommendation (Executive Agent)
        save_status_trace(session_id, "✍️ Executive Agent is synthesizing final consensus recommendation...", db)
        
        final_synthesis_prompt = (
            f"Consolidate everything into a definitive recommendation report for the user query: '{query}'\n\n"
            f"Final inputs:\n"
            f"- Research:\n{research_rep}\n"
            f"- Refined Roadmap:\n{refined_planner}\n"
            f"- Refined Risks:\n{refined_risk}\n"
            f"- Refined Finance:\n{refined_finance}\n"
            f"- Critic Critique:\n{critique}\n"
            f"Structure the final report. Make a definitive career track recommendation. "
            f"Include a comparison matrix, budget/ROI assessment, timeline milestones, and mitigation strategies. "
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
