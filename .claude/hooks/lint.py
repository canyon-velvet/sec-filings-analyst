"""PostToolUse hook: format and auto-fix the Python file Claude just wrote or edited."""

import json
import os
import subprocess
import sys
from pathlib import Path

event = json.load(sys.stdin)
file_path = event["tool_input"]["file_path"]
if not file_path.endswith(".py"):
    sys.exit(0)
project = Path(os.environ.get("CLAUDE_PROJECT_DIR", event["cwd"]))
ruff = project / ".venv" / "bin" / "ruff"
if not ruff.exists():  # project not set up yet (`uv sync` not run)
    sys.exit(0)

subprocess.run(
    [str(ruff), "check", "--fix", "--quiet", file_path], cwd=project, capture_output=True
)
subprocess.run([str(ruff), "format", "--quiet", file_path], cwd=project)
# Judge only what's left after both fixing and formatting.
check = subprocess.run(
    [str(ruff), "check", "--quiet", file_path], cwd=project, capture_output=True, text=True
)
if check.returncode != 0:
    reason = "ruff found errors:\n" + check.stdout + check.stderr  # stderr: ruff/config failures
    print(json.dumps({"decision": "block", "reason": reason}))
