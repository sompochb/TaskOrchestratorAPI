# Task Orchestrator API

Local-first background task orchestration backend for the agent team. SQLite and uploaded files stay on the PC running the server.

## Included agents
- Lauren — Technical Lead / Developer
- John Wick — Software Tester
- Khun Rabiap — Documentation
- Nong Ing — Project Coordinator

## Run on Windows
1. Install Python 3.11+.
2. Open PowerShell in this repository.
3. Run:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open Swagger at `http://localhost:8000/docs`. Health: `http://localhost:8000/health`.

## v0.2 background-agent model
Tasks are persisted in SQLite. Independent pending tasks can be claimed by different workers in parallel. A task with dependencies stays pending until every prerequisite is completed. Workers report completion or failure; failures automatically return to pending until `max_retries` is exceeded.

Example chain: Lauren development -> John Wick test -> Khun Rabiap documentation -> Nong Ing coordination/reporting.

## Core endpoints
- `GET /health`, `GET /agents`
- `GET /tasks`, `GET /tasks/{id}`
- `POST /tasks` — queue a task; optional `depends_on`
- `POST /workflows` — queue a dependency graph; within this request, `depends_on` may use zero-based task indexes as strings
- `POST /worker/claim?agent_id=lauren` — claim the next ready task
- `POST /tasks/{id}/complete?result=...`
- `POST /tasks/{id}/fail?error=...` — retry or mark failed
- `POST /tasks/{id}/cancel`
- `GET /tasks/{id}/logs`
- `POST /tasks/{id}/files`, `GET /tasks/{id}/files`

## Quick test
Create two independent tasks assigned to `lauren` and `john-wick`; each worker can claim its own task immediately. For a chain, create Lauren first, then create John Wick with Lauren's task id in `depends_on`. John Wick cannot claim that task until Lauren is completed.

## Local data
- SQLite: `data/task_orchestrator.db`
- Uploaded files: `data/files/<task-id>/`

Operational data is ignored by Git.
