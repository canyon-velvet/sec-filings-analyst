"""PreToolUse hook: deny unreviewed `git push`es. Never allows; silent for anything else."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

command = json.load(sys.stdin)["tool_input"]["command"]
push = re.search(r"\bgit\s+push\b", command)
if not push:
    sys.exit(0)
push_args = re.split(r"[;&|]", command[push.end() :])[0].split()
project = os.environ["CLAUDE_PROJECT_DIR"]


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=project, capture_output=True, text=True
    ).stdout.strip()


def deny(reason):
    decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny"}
    print(json.dumps({"hookSpecificOutput": {**decision, "permissionDecisionReason": reason}}))
    sys.exit(0)


branch = git("rev-parse", "--abbrev-ref", "HEAD")
if branch == "main" or any(arg == "main" or arg.endswith(":main") for arg in push_args):
    deny("Never push to main: push a branch and open a PR.")

marker = Path(project) / ".claude" / "review-ok"
if not marker.exists() or marker.read_text().strip() != git("rev-parse", "HEAD"):
    deny("HEAD hasn't passed the three pre-push reviews (see CLAUDE.md Workflow).")

merged = subprocess.run(
    ["gh", "pr", "list", "--head", branch, *"--state merged --json number --jq length".split()],
    cwd=project,
    capture_output=True,
    text=True,
).stdout.strip()
if merged != "0":  # also denies when gh fails and prints nothing
    deny(f"A PR from '{branch}' is already merged (or gh couldn't check): branch again from main.")
