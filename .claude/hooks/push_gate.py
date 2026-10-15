"""PreToolUse hook: deny unreviewed `git push`es. Never allows; silent for anything else.

It catches Claude *forgetting* the reviews, not evading them: pushes hidden in `bash -c`,
`eval` or backticks get through. GitHub's `protect-main` ruleset blocks direct pushes to main.
"""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


def deny(reason):
    decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny"}
    print(json.dumps({"hookSpecificOutput": {**decision, "permissionDecisionReason": reason}}))
    sys.exit(0)


def push_args(command):
    """Args after `push` in any `git ... push ...` simple command, or None if there's no push.

    A `push` token anywhere after `git` counts, so global options (`-C dir`, `--work-tree x`)
    can't hide it; quoted text like commit messages is one token, so it never matches.
    """
    command = command.replace("\\\n", " ")  # join continued lines
    # Newline is a separator token, so a `# comment` ends at its line (quotes in it are inert).
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    found, segment = None, []
    for token in [*lexer, ";"]:
        if token and set(token) <= set(";&|()\n"):  # end of a simple command
            names = [Path(word).name for word in segment]  # `/usr/bin/git` -> `git`
            after_git = segment[names.index("git") :] if "git" in names else []
            if "push" in after_git:
                found = (found or []) + after_git[after_git.index("push") + 1 :]
            segment = []
        else:
            segment.append(token)
    return found


def targets_main(arg):
    """`main`, `+main`, `HEAD:main`, `x:refs/heads/main`, `--all`, `--branches`, `--mirror`."""
    ref = arg.split(":")[-1].lstrip("+").removeprefix("refs/heads/")
    return ref == "main" or arg in ("--all", "--branches", "--mirror")


def main():
    command = json.load(sys.stdin)["tool_input"]["command"]
    args = push_args(command) if "push" in command else None
    if args is None:
        return
    project = os.environ["CLAUDE_PROJECT_DIR"]

    def run(*args):
        return subprocess.run(args, cwd=project, capture_output=True, text=True).stdout.strip()

    branch = run("git", "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "main" or any(targets_main(arg) for arg in args):
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
