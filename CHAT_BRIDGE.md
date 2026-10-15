# Chat-to-Task bridge (opt-in)

This bridge allows a GitHub issue created from ChatGPT to be queued on your PC. It does **not** make localhost reachable from ChatGPT.

## PC setup (PowerShell)
1. Pull this branch after review, or merge its PR.
2. Set `GITHUB_TOKEN` to a GitHub fine-grained token with **Issues: read** on this repository. Never paste the token into chat or commit it.
3. Optionally set `BRIDGE_REPO` and `BRIDGE_OWNER` (defaults: `sompochb/TaskOrchestratorAPI`, `sompochb`).
4. Keep the API and Codex workers running. Start `python github_issue_bridge.py` in another terminal.
5. For each issue you want to run, add its issue number to `approved_issues.txt` (one number per line). This is a **local approval gate**; no task executes without it.

## Issue format
Title: `[Agent Task] Review Task Orchestrator`

Body:
```json
{
  "title": "Review Task Orchestrator",
  "description": "Review source code, run available tests, report findings; do not modify files.",
  "assigned_agent": "lauren"
}
```

Only issues authored by the configured owner, with the exact prefix and local approval, are queued. The bridge polls every 30 seconds and stores processed issue numbers in `data/bridge_seen.json`. Do not delete this file unless you intend to risk duplicate jobs.

## Security and limitations
- Never expose the unauthenticated Task API to the public internet; bind it to localhost or firewall it.
- GitHub issue text is untrusted instructions passed to Codex; approve only reviewed tasks and use a restricted workspace.
- The bridge **does not** automatically post results back to ChatGPT; ask ChatGPT to check GitHub and use local Swagger for actual results until a reporting bridge is implemented.
- This is a prototype. It does not yet provide remote status syncing, retries, or robust audit controls.
