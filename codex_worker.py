"""Run a local Codex CLI agent against queued Task Orchestrator tasks.

Requires: Codex CLI installed and authenticated on this machine.
Run one process per agent with its own trusted workspace.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

LOG = logging.getLogger("codex-worker")


def api(base, method, path, params=None, timeout=30):
    url = base.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def run_task(task, workspace, agent, codex, timeout, base):
    task_id = task["id"]
    prompt = (
        f"You are {agent}, a software project agent. Execute this assigned task "
        "in the current working directory. Follow repository instructions. "
        "Do not access secrets or files outside this workspace. "
        "Report concrete changes and verification results.\n\n"
        f"Title: {task['title']}\n"
        f"Description: {task.get('description') or ''}\n"
    )
    # No shell=True: task text is passed as a single argument, not executable shell.
    command = [codex, "exec", "--cd", str(workspace), "--skip-git-repo-check", prompt]
    LOG.info("Starting %s for task %s", agent, task_id)
    try:
        result = subprocess.run(command, cwd=workspace, capture_output=True, text=True,
                                timeout=timeout, check=False)
        summary = (result.stdout or "")[-12000:]
        if result.returncode:
            error = ((result.stderr or "") + "\n" + summary)[-4000:]
            api(base, "POST", f"/tasks/{task_id}/fail", {"error": error or f"Codex exited {result.returncode}"})
            LOG.error("Task %s failed (exit %s)", task_id, result.returncode)
        else:
            api(base, "POST", f"/tasks/{task_id}/complete", {"result": summary or "Codex exited successfully"})
            LOG.info("Task %s completed", task_id)
    except subprocess.TimeoutExpired:
        api(base, "POST", f"/tasks/{task_id}/fail", {"error": f"Codex timed out after {timeout}s"})
        LOG.error("Task %s timed out", task_id)


def main():
    parser = argparse.ArgumentParser(description="Local Codex worker for Task Orchestrator")
    parser.add_argument("--agent", choices=["lauren", "john-wick"], required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--api", default=os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    workspace = args.workspace.resolve(strict=True)
    if not workspace.is_dir():
        parser.error("--workspace must be a directory")
    if args.interval < 1 or args.timeout < 1:
        parser.error("--interval and --timeout must be positive")
    codex = shutil.which("codex")
    if not codex:
        parser.error("Codex CLI not found in PATH; install it and authenticate first")
    LOG.info("Worker %s listening at %s, workspace=%s", args.agent, args.api, workspace)
    while True:
        try:
            claimed = api(args.api, "POST", "/worker/claim", {"agent_id": args.agent})
            task = claimed.get("task") if "task" in claimed else claimed
            if task and task.get("id"):
                run_task(task, workspace, args.agent, codex, args.timeout, args.api)
            else:
                time.sleep(args.interval)
        except KeyboardInterrupt:
            LOG.info("Worker stopped")
            break
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            LOG.warning("API/worker error: %s", exc)
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
