# Submission Writeup: LifePilot AI

## 1. Problem Statement
Making high-stakes life decisions—such as career transitions, educational pathways, and financial investments—is a highly complex, multi-dimensional problem. Individuals often struggle to balance market demand, learning curves, financial readiness, timeline constraints, and personal risks simultaneously. Information is scattered, and generic advice lacks personalization. 

**LifePilot AI** solves this by providing a unified, secure, and secure AI-driven decision operating system. It brings together a team of specialized agents—orchestrated under Google ADK 2.0—to research trends, design custom timelines, calculate financial return on investment (ROI), evaluate potential roadblocks, and engage in constructive debate to deliver a consolidated, optimized, and rigorous recommendation report.

---

## 2. Solution Architecture

The system is structured as a directed graph workflow managed by the **Google ADK 2.0 graph engine**:

```
                  [ USER QUERY ]
                        │
                        ▼
            ┌───────────────────────┐
            │  security_checkpoint  │ ◄─── Logs to artifacts/security_audit.json
            └───────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         │ (SECURITY_EVENT)            │ (PASSED)
         ▼                             ▼
  ┌──────────────┐             ┌──────────────┐
  │   security   │             │ orchestrator │
  │   blocked    │             │  (Executive  │
  │   node       │             │    Agent)    │
  └──────────────┘             │    Node      │
         │                     └──────────────┘
         │                             │
         │              ┌──────────────┼──────────────┬──────────────┐
         │              ▼              ▼              ▼              ▼
         │       ┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐
         │       │ResearchAgent ││ PlannerAgent ││  RiskAgent  ││ FinanceAgent │
         │       └──────────────┘└──────────────┘└──────────────┘└──────────────┘
         │              │              │                             │
         │              └──────────────┼──────────────┬──────────────┘
         │                             ▼
         │                      ┌──────────────┐
         │                      │ CriticAgent  │ (Debate and Refinement)
         │                      └──────────────┘
         │                             │
         │                             ▼
         │                     ┌──────────────┐
         │                     │ orchestrator │ (Synthesizes report)
         │                     └──────────────┘
         │                             │
         │              ┌──────────────┴──────────────┐
         │              │ (NEEDS_APPROVAL)            │ (AUTO_APPROVED)
         │              ▼                             │
         │       ┌──────────────┐                     │
         │       │human_approval│                     │
         │       │(RequestInput)│                     │
         │       └──────────────┘                     │
         │              │                             │
         │              └──────────────┬──────────────┘
         │                             ▼
         └──────────────────────► ┌───────────┐
                                  │   final   │ ───► [ OUTPUT REPORT ]
                                  │ synthesis │
                                  └───────────┘
```

---

## 3. Core Concepts Used

Our implementation leverages the core building blocks of the **Google ADK 2.0** framework:

*   **ADK 2.0 Workflow Graph**: Configured in [app/agent.py](file:///c:/Users/aasis/Documents/New%20folder/lifepilot-ai/app/agent.py#L225-L255). We build a static directed graph using `Workflow` and `Edge` classes with designated node transitions. Control flow is routed dynamically using `ctx.route` inside function nodes.
*   **LlmAgent**: Implemented in [app/agent.py](file:///c:/Users/aasis/Documents/New%20folder/lifepilot-ai/app/agent.py#L51-L150) for the orchestrator and all five specialists (Research, Planner, Risk, Finance, Critic).
*   **AgentTool**: Described in [app/agent.py](file:///c:/Users/aasis/Documents/New%20folder/lifepilot-ai/app/agent.py#L143-L150). The `ExecutiveAgent` wraps sub-agents inside `AgentTool` instances. This allows the top-level coordinator to seamlessly delegate complex tasks to specialist sub-agents during LLM planning cycles.
*   **Model Context Protocol (MCP) Server**: Implemented in [app/mcp_server.py](file:///c:/Users/aasis/Documents/New%20folder/lifepilot-ai/app/mcp_server.py). A fast python stdio server that exposes four domain-specific tools: web search, writing files, calendar milestone bookings, and ROI calculators. We wire the `McpToolset` directly into our agents in `app/agent.py` so they can communicate with our local server.
*   **Security Checkpoint**: Configured as a Workflow function node in [app/agent.py](file:///c:/Users/aasis/Documents/New%20folder/lifepilot-ai/app/agent.py#L159-L210). It intercept inputs, scrubs PII, scans for injections, and logs metadata.
*   **Agents CLI**: Scaffolded using `agents-cli scaffold create lifepilot-ai --deployment-target agent_runtime`, generating our standard directory structure, manifest, and configuration models.

---

## 4. Security Design

We have implemented a robust, defense-in-depth security model to safeguard user transactions and model interactions:

*   **PII Redaction**: Standard regular expressions scrub emails, phone numbers, and Aadhaar/SSN formats, replacing them with placeholders like `[REDACTED_EMAIL]`. This prevents sensitive personal data from leaking to the external Gemini model.
*   **Prompt Injection Mitigation**: A keyword scanning filter intercepts input prompts before graph execution. If bypass attempts or jailbreaks (e.g., `ignore previous instructions`, `system override`) are found, the node triggers a `SECURITY_EVENT` route, bypassing all agent nodes and shutting down execution immediately.
*   **Structured Audit Logging**: Every query execution compiles safety metadata (lengths, PII flags, injection indicators, severity) and appends a structured JSON block to a secure file `artifacts/security_audit.json` for security compliance monitoring.
*   **Sandboxing**: All file writes and calendar milestones are strictly verified inside a local `sandbox/` directory using path-traversal validation checks (`validate_path`) to block any directory escape attempts.

---

## 5. MCP Server Design

The system runs a local stdio MCP server that exposes four domain-specific capabilities:

1.  **`mcp_web_search`**: Leverages `duckduckgo_search` text queries. This gives the `ResearchAgent` access to live, real-time market wages, job openings, and course availability without requiring external API tokens or costs.
2.  **`mcp_write_file`**: Allows the `PlannerAgent` to write formatted markdown roadmaps (`roadmap.md`) to the sandbox folder.
3.  **`mcp_create_calendar_milestone`**: Appends milestone dates to a structured `calendar.json` file inside the sandbox.
4.  **`mcp_calculate_finance_roi`**: Performs educational ROI math, calculating compound savings growth, cost-to-benefit returns, and projected career earnings.

---

## 6. Human-in-the-Loop (HITL) Flow

To prevent unauthorized file writes or calendar modifications, we implement a **Human-in-the-Loop (HITL)** guardrail. 

If the `ExecutiveAgent` plans to output roadmaps or schedule phases, the `orchestrator_node` routes the workflow to the `human_approval` node. 
Inside `human_approval`, we yield a `RequestInput` event, which suspends the workflow graph runner and prompts the user in the UI to approve or deny the action. 

When the user clicks "Allow" or "Deny", the runner resumes, passing the response back to the node context (`ctx.resume_inputs`). The node writes the approval decision to `ctx.state` and routes to `final_synthesis`. If approved, files are committed; if rejected, writes are rolled back, ensuring complete user control over local resources.

---

## 7. Demo Walkthrough
*   **Test Case 1 (Standard Flow)**: Shows the complete collaborative pipeline. The Research Agent queries salaries, the Planner schedules milestones, the Finance Agent runs the ROI calculator, the Critic challenges assumptions, and the user interactively approves sandbox writes.
*   **Test Case 2 (Injection Bypass)**: Shows the security checkpoint immediately catching a jailbreak, writing a `CRITICAL` log, and lighting up the red "blocked" path.
*   **Test Case 3 (PII Redaction)**: Demonstrates candidate privacy, replacing private emails and phone numbers with redaction badges.

---

## 8. Impact & Value Statement

LifePilot AI transforms career and financial counseling:
*   **Individuals & Career Changers**: Gain a comprehensive, objective, and financially grounded roadmap tailormade for their budget and timeline.
*   **Financial Advisories**: Benefit from rigorous risk-and-ROI calculations based on live market statistics.
*   **Organizations**: Can deploy this as an internal skill advisor, ensuring employees get secure, PII-scrubbed advice on career progression and development plans.
