"""Poll owner-authored GitHub issues and queue approved tasks to local Task Orchestrator.

Requires GITHUB_TOKEN with Issues read access and ORCHESTRATOR_URL (localhost).
Only issues created by the configured owner, with the exact title prefix, are considered.
For safety, require a local approval file listing issue numbers (one per line).
"""
import json
import os
import time
import urllib.request
from pathlib import Path

REPO = os.getenv("BRIDGE_REPO", "sompochb/TaskOrchestratorAPI")
OWNER = os.getenv("BRIDGE_OWNER", "sompochb")
API = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.environ["GITHUB_TOKEN"]
APPROVED = Path(os.getenv("BRIDGE_APPROVED_FILE", "approved_issues.txt"))
SEEN = Path(os.getenv("BRIDGE_SEEN_FILE", "data/bridge_seen.json"))
PREFIX = "[Agent Task] "

def request(url, method="GET", payload=None, github=False):
    headers = {"Accept": "application/vnd.github+json" if github else "application/json"}
    if github:
        headers["Authorization"] = "Bearer " + TOKEN
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    data = json.dumps(payload).encode() if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=20) as r:
        return json.load(r)

def poll():
    allowed = set(APPROVED.read_text().split()) if APPROVED.exists() else set()
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    seen = json.loads(SEEN.read_text()) if SEEN.exists() else {}
    issues = request(f"https://api.github.com/repos/{REPO}/issues?state=open&per_page=100", github=True)
    for issue in reversed(issues):
        number = str(issue["number"])
        if number not in allowed or number in seen or "pull_request" in issue:
            continue
        if issue["user"]["login"].lower() != OWNER.lower() or not issue["title"].startswith(PREFIX):
            continue
        try:
            task = json.loads(issue.get("body") or "")
            if not isinstance(task, dict) or task.get("assigned_agent") not in ("lauren", "john-wick"):
                raise ValueError("Invalid agent")
            task = {
                "title": str(task["title"])[:200],
                "description": str(task["description"])[:12000],
                "assigned_agent": task["assigned_agent"],
                "depends_on": [],
                "max_retries": 0,
            }
            result = request(API + "/tasks", "POST", task)
            seen[number] = result["id"]
            SEEN.write_text(json.dumps(seen, indent=2))
            print(f"Issue #{number} queued as {result['id']}", flush=True)
        except (ValueError, KeyError) as exc:
            print(f"Issue #{number} skipped: {exc}", flush=True)

if __name__ == "__main__":
    print("Bridge started. Only locally approved, owner-authored issues are eligible.", flush=True)
    while True:
        try:
            poll()
        except Exception as exc:
            print(f"Bridge polling error: {exc}", flush=True)
        time.sleep(30)
