import os
from google.adk import Agent
from ..mcp.tools import (
    web_search, read_file, write_file, list_files,
    create_calendar_event, calculate_roi
)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Research Agent: Gathers current trends, facts, salary ranges, and courses
research_agent = Agent(
    name="ResearchAgent",
    model=MODEL_NAME,
    description="Researches current job trends, technologies, market demands, and online courses.",
    instruction=(
        "You are an expert Research Agent. Your goal is to gather accurate, current information about "
        "career tracks, tech stacks, market demand, salary trends, and learning resources. "
        "To keep execution fast, perform at most 1 or 2 high-quality, consolidated web searches total. "
        "Avoid making many individual search calls. Focus on facts, statistics, and concrete data points, "
        "and present your findings clearly and structured."
    ),
    tools=[web_search]
)

# Planner Agent: Generates detailed roadmaps and timelines, writes them to files
planner_agent = Agent(
    name="PlannerAgent",
    model=MODEL_NAME,
    description="Creates step-by-step educational roadmaps and writes files.",
    instruction=(
        "You are an expert Planner Agent. Your goal is to map out detailed step-by-step career and learning roadmaps "
        "based on the research findings. Break down timelines (e.g. months, weeks), estimate hours per day, "
        "suggest projects to build, and list milestones. Use the write_file tool to save the roadmap to the sandbox. "
        "Ensure your timeline is realistic for the user's budget and constraints."
    ),
    tools=[write_file]
)

# Risk Agent: Evaluates blockers, failure rates, competition, and difficulties
risk_agent = Agent(
    name="RiskAgent",
    model=MODEL_NAME,
    description="Identifies potential career risks, skill gaps, learning difficulties, and market saturation.",
    instruction=(
        "You are an expert Risk Agent. Your goal is to analyze potential risks, failure points, and difficulties "
        "associated with each decision option. Evaluate market saturation, competition levels, difficult concepts "
        "that cause learners to quit, and potential roadblocks (e.g., lack of job openings for freshers). "
        "Provide constructive advice on how to mitigate these risks."
    ),
    tools=[read_file]
)

# Finance Agent: Performs cost analysis, salary projection, and ROI calculations
finance_agent = Agent(
    name="FinanceAgent",
    model=MODEL_NAME,
    description="Estimates costs, future salary projections, ROI, and budget management.",
    instruction=(
        "You are an expert Finance Agent. Your goal is to calculate financial outcomes. "
        "Analyze the cost of courses, certifications, living expenses during the learning phase, and "
        "compare it against expected salaries (starting and long-term). Use the calculate_roi tool "
        "to estimate financial growth, return on investment, and budget feasibility. Make sure "
        "all calculations are detailed and ₹ (INR) or $ (USD) based."
    ),
    tools=[calculate_roi, read_file]
)

# Critic Agent: Critiques agent drafts, challenges assumptions, and enforces rigor
critic_agent = Agent(
    name="CriticAgent",
    model=MODEL_NAME,
    description="Evaluates reports, challenges assumptions, details weak spots, and drives consensus.",
    instruction=(
        "You are the Critic Agent. Your role is to examine the analysis, roadmaps, risk assessments, "
        "and financial projections made by other agents. Identify gaps, weak arguments, overly optimistic "
        "projections, or contradictions. Challenge their assumptions (e.g. 'Can someone really learn AI engineering "
        "in 8 months on that budget?'). Ask hard questions to force them to refine their outputs and "
        "produce a more rigorous final decision."
    ),
    tools=[]
)
