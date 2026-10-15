"""PreToolUse hook: deny unreviewed `git push`es. Never allows; silent for anything else."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Allows git's global options before `push`, e.g. `git -C path push`, `git -c k=v push`.
PUSH = re.compile(r"\bgit(?:\s+(?:-[Cc]\s+\S+|-\S+))*\s+push\b")


def deny(reason):
    decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny"}
    print(json.dumps({"hookSpecificOutput": {**decision, "permissionDecisionReason": reason}}))
    sys.exit(0)


def targets_main(arg):
    """`main`, `'main'`, `+main`, `HEAD:main`, `x:refs/heads/main`, `--all`, `--mirror`."""
    ref = arg.strip("'\"").split(":")[-1].lstrip("+").removeprefix("refs/heads/")
    return ref == "main" or arg in ("--all", "--mirror")


def main():
    command = json.load(sys.stdin)["tool_input"]["command"]
    push = PUSH.search(command)
    if not push:
        return
    push_args = re.split(r"[;&|]", command[push.end() :])[0].split()
    project = os.environ["CLAUDE_PROJECT_DIR"]

    def run(*args):
        return subprocess.run(args, cwd=project, capture_output=True, text=True).stdout.strip()

    branch = run("git", "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "main" or any(targets_main(arg) for arg in push_args):
        deny("Never push to main: push a branch and open a PR.")

    marker = Path(project) / ".claude" / "review-ok"
    if not marker.exists() or marker.read_text().strip() != run("git", "rev-parse", "HEAD"):
        deny("HEAD hasn't passed the three pre-push reviews (see CLAUDE.md Workflow).")

    gh_args = ["--head", branch, "--state", "merged", "--json", "number", "--jq", "length"]
    if run("gh", "pr", "list", *gh_args) != "0":  # also denies when gh prints nothing
        deny(f"'{branch}' already has a merged PR (or gh couldn't check): branch again from main.")


try:
    main()
except Exception as error:  # a crashing PreToolUse hook doesn't block, so fail closed
    deny(f"Push gate failed ({error!r}); not pushing.")
