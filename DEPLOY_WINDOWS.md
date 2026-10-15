# Windows Mini PC deployment preparation

This repository currently exposes a local FastAPI task queue, not verified autonomous agent executors.

## Local validation
1. Install Python 3.11+ and Git on the Mini PC.
2. Clone the repository and open PowerShell in its directory.
3. Run `powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1`.
4. In a second PowerShell terminal, run `powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1`.
5. Visit `http://127.0.0.1:8000/docs`.

## Release blockers
- Do **not** port-forward 8000 or expose the API to the internet: endpoints currently lack production authentication.
- Implement and test actual agent worker executors, concurrency, recovery, and reporting before claiming agents work autonomously.
- Add authentication, file-upload limits and validation, service auto-restart, SQLite backups, rollback, and negative tests.
- Only after QA passes, install as a managed Windows service and verify on the owner's PC.

SQLite data lives under `data/`; include this directory in protected offline backups. Never commit production data or secrets.
