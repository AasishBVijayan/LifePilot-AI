# LifePilot AI: Decision-Making Agent Operating System

LifePilot AI is an AI-powered decision-making operating system where specialized agents collaborate to help users make important career, educational, business, and financial decisions. 

Built using the **Google Agent Development Kit (ADK)** and powered by Gemini, it features a futuristic **Mission Control Dashboard** displaying real-time agent logic streams, parallel execution charts, tool logs, and interactive human-in-the-loop security approval popups.

---

## Key Features

1. **Google ADK multi-agent orchestration**: Uses sequential, parallel, and dynamic workflows to manage agent execution.
2. **Debate & Consensus Framework**: A structured cycle where specialized agents draft plans, the **Critic Agent** challenges assumptions, agents refine their plans, and the **Executive Agent** compiles a final report.
3. **Antigravity Agent Builder**: Automatically compiles, tests, configures, and registers brand-new agents in real time based on natural language commands (e.g., *"Create a Startup Advisor Agent"*).
4. **MCP-Equivalent Tools**: Exposes Web Search (DuckDuckGo), File Manipulation, Calendar scheduling, and ROI Calculators to agents.
5. **Interactive Tool Safety Interceptor**: Pauses execution and prompts the user in the UI to approve or deny dangerous operations (like file writes or calendar modifications).
6. **Prompt Injection Protection**: Heuristic and pattern analysis layers checking inputs before model delegation.

---

## Folder Structure

```
lifepilot-ai/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── dynamic/        # Custom generated agent files (configs, prompts, tests, Dockerfiles)
│   │   │   ├── orchestrator.py # Multi-agent ADK execution graph
│   │   │   ├── executive.py    # Executive Agent configurations
│   │   │   ├── specialist.py   # Specialist agents config (Research, Planner, Risk, Finance, Critic)
│   │   │   └── dynamic_loader.py # Dynamically loads custom user-created agents
│   │   ├── mcp/
│   │   │   └── tools.py        # Web, File, Calendar, Finance tools implementations
│   │   ├── database.py         # SQLite connection and schema setup
│   │   ├── models.py           # SQLAlchemy database tables
│   │   ├── security.py         # Prompt injection and tool safety approvals
│   │   ├── builder.py          # Antigravity dynamic agent compiler
│   │   └── main.py             # FastAPI REST endpoints and SSE stream generator
│   ├── .env.example            # Environment variables template
│   └── Dockerfile              # Docker container configuration
├── frontend/
│   └── index.html              # Futuristic Mission Control dashboard SPA
├── sandbox/                    # Directory for sandboxed File MCP reads/writes
├── docker-compose.yml          # Container configuration
└── README.md                   # This documentation
```

---

## Setup & Local Installation

### Prerequisites
* Python 3.10 or higher
* Google Gemini API Key

### Step 1: Clone and Initialize Virtual Environment
Open PowerShell (or your terminal) and run:
```powershell
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate
```

### Step 2: Install Dependencies
```powershell
pip install -r backend/requirements.txt
```

### Step 3: Configure environment variables (Add API Key)
Copy the environment variables template and add your Gemini API Key:
```powershell
cp backend/.env.example backend/.env
```
Open `backend/.env` and replace `your_gemini_api_key_here` with your active key:
```env
GEMINI_API_KEY=AIzaSyD...
GEMINI_MODEL=gemini-2.5-flash
```

### Step 4: Run the Application
Start the FastAPI server:
```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open your browser and navigate to:
👉 **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

---

## Docker Deployment

You can deploy the entire stack instantly using Docker Compose:
1. Ensure your `.env` contains your `GEMINI_API_KEY`.
2. Run:
   ```bash
   docker-compose up --build
   ```
3. Open `http://localhost:8000/` in your browser.

---

## Hackathon Demo Script

Here is a step-by-step walkthrough to present a winning demo:

### Phase 1: The Core Value Proposition & UI
1. Load `http://127.0.0.1:8000/` in front of the judges. Point out the dark glassmorphic **Mission Control** interface and explain that they are looking at an agentic operating system.
2. Show the preloaded query: *"I have ₹50,000 and 8 months. Should I learn AI Engineering, Cybersecurity, or Data Engineering?"*
3. Point out that the budget (₹50,000) and time (8 months) are hard constraints that the agents must evaluate.

### Phase 2: Live Multi-Agent Execution & Parallelism
1. Click **Analyze Strategy**.
2. Show the **Agent Boarding Chart** immediately light up:
   * Executive Agent turns blue (`THINKING`) as it deconstructs the request.
   * Then, the Research, Planner, Risk, and Finance agents light up in green/gold (`THINKING` / `TOOL_CALL`) **in parallel**.
3. Point out the **Agent Collaboration Terminal** scrolling in real time, showing the distinct reasoning lines of each agent.

### Phase 3: Human-in-the-Loop Security & MCP Tools
1. Draw the judges' attention to the **Security Approval Required** prompt popping up at the top of the terminal.
2. Explain: *"The Planner Agent wants to schedule a milestone in the virtual calendar, and the security layer has intercepted the execution. Nothing runs without user consent."*
3. Click **Allow Execution**. Watch the terminal resume, showing the tool response.
4. Click the **Sandbox Repository** file list on the left. Click on `roadmap.md` and show them the beautiful learning roadmap written to the sandbox by the agent.

### Phase 4: Debate, Consensus, and Final Report
1. Scroll down the terminal to highlight the **Critic Agent** challenging assumptions: *"CHALLENGE: A budget of ₹50,000 is tight for professional bootcamps. Learning AI engineering requires GPUs which adds infrastructure costs..."*
2. Show the specialists revising their plans in response to the Critic.
3. Show the final synthesized **Career Recommendation Report** at the bottom of the page, presenting a clean ranking, risk analysis table, and financial projections.

### Phase 5: The Antigravity Agent Builder (Wow Factor)
1. Type: `Create a Startup Advisor Agent` in the Agent Builder input.
2. Click **Compile New Agent**.
3. Explain: *"In the background, Gemini is compiling a new agent configuration, generating a tailored system prompt, selecting tools, writing a python test suite, creating a Dockerfile, and registering it dynamically."*
4. Once completed, show the new agent card immediately register in the **Agent Boarding Chart** under "Custom Dynamic Agents", ready to participate in the next decision query!
