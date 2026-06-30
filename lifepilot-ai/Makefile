# Makefile for LifePilot AI (Google ADK 2.0 & MCP)

.PHONY: install playground run test clean

install:
	uv sync

playground:
	uv run adk web app --host 127.0.0.1 --port 18081 --reload_agents

run:
	uv run python -m uvicorn app.agent_runtime_app:app --host 127.0.0.1 --port 8000

test:
	uv run pytest tests/

clean:
	rm -rf .adk/ .venv/ __pycache__/ *.db artifacts/sandbox/
