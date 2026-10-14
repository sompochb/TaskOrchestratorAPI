# Task Orchestrator API

Local-first task orchestration backend for the agent team. SQLite and uploaded files stay on the PC running the server.

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

Open API documentation at `http://localhost:8000/docs`.
Health check: `http://localhost:8000/health`.

## Local data
- SQLite: `data/task_orchestrator.db`
- Uploaded files: `data/files/<task-id>/`

Both are ignored by Git so operational data stays on the server PC.

## MVP endpoints
- `GET /health`
- `GET /agents`
- `GET /tasks`
- `POST /tasks`
- `PATCH /tasks/{task_id}`
- `POST /tasks/{task_id}/files`
- `GET /tasks/{task_id}/files`

Next phase: authentication/API keys, task dependencies and handoffs, agent heartbeat/queue, audit log, file download, and coordinator notifications.
