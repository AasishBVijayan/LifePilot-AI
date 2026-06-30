import asyncio
import os
import json
import logging
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Load env variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

from .database import init_db, get_db
from .models import SessionModel, AgentTraceModel, ToolApprovalModel, DynamicAgentModel
from .agents.orchestrator import run_lifepilot_workflow
from .builder import build_and_register_agent
from .security import check_prompt_injection, SANDBOX_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lifepilot.main")

app = FastAPI(title="LifePilot AI - Multi-Agent Operating System")

# Configure CORS for local React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)

# DB Initialization
@app.on_event("startup")
def startup_event():
    init_db()
    logger.info("SQLite Database initialized and tables created.")

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "index.html"))
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail=f"Frontend file not found at {html_path}")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

class QueryRequest(BaseModel):
    query: str

class ApprovalRequest(BaseModel):
    status: str  # APPROVED or DENIED

class BuildAgentRequest(BaseModel):
    prompt: str

@app.post("/api/query")
def start_query_session(request: QueryRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Starts a new multi-agent decision session. Checks for prompt injections first.
    Runs the agent workflow in the background.
    """
    query_text = request.query.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    # Security prompt injection filter
    injected, reason = check_prompt_injection(query_text)
    if injected:
        raise HTTPException(status_code=400, detail=f"Security Alert: {reason}")
        
    # Generate unique session ID
    import time
    session_id = f"sess_{int(time.time() * 1000)}"
    
    # Save session
    session = SessionModel(id=session_id, query=query_text, status="PENDING")
    db.add(session)
    
    # Add initial status trace
    init_trace = AgentTraceModel(
        session_id=session_id,
        agent_name="System",
        step_type="STATUS",
        content="Session queued. Waiting for worker initiation."
    )
    db.add(init_trace)
    db.commit()
    
    # Trigger multi-agent workflow in the background
    background_tasks.add_task(run_lifepilot_workflow, session_id, query_text, db)
    
    return {"session_id": session_id, "status": "PENDING"}

@app.get("/api/sessions/{session_id}")
def get_session_details(session_id: str, db: Session = Depends(get_db)):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": session.id,
        "query": session.query,
        "status": session.status,
        "final_report": session.final_report,
        "created_at": session.created_at
    }

@app.get("/api/stream/{session_id}")
async def stream_session_events(session_id: str):
    """
    Server-Sent Events (SSE) endpoint to stream real-time traces and approvals to the frontend.
    """
    async def sse_event_generator():
        # Clean session retrieval helper
        db = next(get_db())
        sent_trace_ids = set()
        sent_approval_ids = set()
        
        while True:
            # Refresh session to check status
            db.expire_all()
            session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if not session:
                yield "event: error\ndata: Session not found\n\n"
                break
                
            # Get unsent traces
            traces = db.query(AgentTraceModel).filter(
                AgentTraceModel.session_id == session_id
            ).order_by(AgentTraceModel.id.asc()).all()
            
            for t in traces:
                if t.id not in sent_trace_ids:
                    data = {
                        "id": t.id,
                        "agent_name": t.agent_name,
                        "step_type": t.step_type,
                        "content": t.content,
                        "meta_data": json.loads(t.meta_data) if t.meta_data else None,
                        "created_at": t.created_at.isoformat()
                    }
                    yield f"event: trace\ndata: {json.dumps(data)}\n\n"
                    sent_trace_ids.add(t.id)
                    
            # Get pending approvals
            approvals = db.query(ToolApprovalModel).filter(
                ToolApprovalModel.session_id == session_id,
                ToolApprovalModel.status == "PENDING"
            ).all()
            
            for app in approvals:
                if app.id not in sent_approval_ids:
                    data = {
                        "id": app.id,
                        "agent_name": app.agent_name,
                        "tool_name": app.tool_name,
                        "arguments": json.loads(app.arguments)
                    }
                    yield f"event: approval_required\ndata: {json.dumps(data)}\n\n"
                    sent_approval_ids.add(app.id)
            
            # If session is complete or failed, send final status update and close
            if session.status in ["COMPLETED", "FAILED"]:
                # Yield a final trace sweep before closing
                await asyncio.sleep(0.5)
                yield f"event: done\ndata: {session.status}\n\n"
                break
                
            await asyncio.sleep(0.5)
            
    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")

@app.post("/api/approvals/{approval_id}")
def handle_tool_approval(approval_id: str, request: ApprovalRequest, db: Session = Depends(get_db)):
    """
    Submits user choice (APPROVED or DENIED) to resolve blocked tool execution.
    """
    approval = db.query(ToolApprovalModel).filter(ToolApprovalModel.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
        
    status = request.status.upper()
    if status not in ["APPROVED", "DENIED"]:
        raise HTTPException(status_code=400, detail="Invalid approval status. Must be APPROVED or DENIED.")
        
    approval.status = status
    db.commit()
    return {"status": status}

@app.post("/api/build-agent")
def create_custom_agent(request: BuildAgentRequest, db: Session = Depends(get_db)):
    """
    Antigravity Feature: Dynamically builds and registers an agent.
    """
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Agent build prompt cannot be empty.")
    try:
        res = build_and_register_agent(prompt, db)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate agent: {str(e)}")

@app.get("/api/agents")
def list_available_agents(db: Session = Depends(get_db)):
    """
    Lists static expert agents + custom database-registered agents.
    """
    static_agents = [
        {"name": "ExecutiveAgent", "role": "Orchestration & Synthesis", "tools": []},
        {"name": "ResearchAgent", "role": "Market Trends & Fact Finding", "tools": ["web_search"]},
        {"name": "PlannerAgent", "role": "Roadmaps & Timelines", "tools": ["write_file", "read_file", "create_calendar_event"]},
        {"name": "RiskAgent", "role": "Blockers & Competition Analysis", "tools": ["read_file"]},
        {"name": "FinanceAgent", "role": "ROI & Cost Estimations", "tools": ["calculate_roi"]},
        {"name": "CriticAgent", "role": "Internal Debate & Validation", "tools": []}
    ]
    
    db_agents = db.query(DynamicAgentModel).all()
    dynamic_list = []
    for a in db_agents:
        dynamic_list.append({
            "name": a.name,
            "role": f"Custom: {a.description}",
            "tools": json.loads(a.tools_config),
            "custom": True
        })
        
    return static_agents + dynamic_list

@app.get("/api/sandbox/files")
def list_sandbox_files():
    """
    Lists files created in the sandbox (e.g. roadmap.md, calendar.json)
    """
    try:
        files = os.listdir(SANDBOX_DIR)
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sandbox/files/{filename}")
def get_sandbox_file(filename: str):
    """
    Retrieves the raw text contents of a sandbox file.
    """
    safe_path = os.path.join(SANDBOX_DIR, filename)
    if not os.path.exists(safe_path) or not os.path.commonpath([SANDBOX_DIR, safe_path]) == SANDBOX_DIR:
        raise HTTPException(status_code=404, detail="File not found or access denied")
    try:
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
