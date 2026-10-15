import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
HOOK = ROOT / ".claude" / "hooks" / "push_gate.py"
FAKES = ROOT / "tests" / "fakes"


def git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def make_repo(tmp_path, branch="feature"):
    """A throwaway repo with one commit, checked out on `branch`."""
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "commit", "--allow-empty", "-m", "init")
    if branch != "main":
        git(tmp_path, "checkout", "-b", branch)
    return tmp_path


def run_gate(repo, command, gh_output="0"):
    payload = {
        "hook_event_name": "PreToolUse",
        "cwd": str(repo),
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={
            "CLAUDE_PROJECT_DIR": str(repo),
            "PATH": f"{FAKES}:{os.environ['PATH']}",
            "FAKE_GH_OUTPUT": gh_output,
        },
    )


@pytest.mark.parametrize(
    "command", ["git commit -m 'push the fix'", 'git commit -m "gate any git push to main"']
)
def test_says_nothing_about_commands_that_are_not_pushes(tmp_path, command):
    repo = make_repo(tmp_path)

    result = run_gate(repo, command)

    assert result.returncode == 0
    assert result.stdout == ""


def denial(result):
    """The deny reason, or None if the gate didn't deny."""
    assert result.returncode == 0
    if not result.stdout:
        return None
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    return output["permissionDecisionReason"]


@pytest.mark.parametrize(
    ("branch", "command"),
    [
        ("main", "git push"),
        ("feature", "git push origin main"),
        ("feature", "git push origin HEAD:main"),
        ("feature", "git -C . push origin main"),
        ("feature", "git -c core.pager=cat push origin main"),
        ("feature", "git push --force origin +main"),
        ("feature", "git push origin feature:refs/heads/main"),
        ("feature", "git push origin 'main'"),
        ("feature", "git push --all origin"),
        ("feature", "git push --branches origin"),
        ("feature", 'git push origin HEAD:"main"'),
        ("feature", "git --work-tree . push origin main"),
        ("feature", "git --namespace x push origin main"),
        ("feature", "# deploy\ngit push origin main"),
        ("feature", "# Let's ship\ngit push origin main\n# then it's done"),
        ("feature", "echo PR#5 && git push origin main"),
        ("feature", "[ $# -eq 0 ] && git push origin main"),
        ("feature", "git push \\\n  origin main"),
        ("feature", "/usr/bin/git push origin main"),
    ],
)
def test_denies_a_push_to_main(tmp_path, branch, command):
    repo = make_repo(tmp_path, branch)

    assert "main" in denial(run_gate(repo, command))


def mark_reviewed(repo):
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "review-ok").write_text(head)


def test_denies_a_push_without_a_review_marker(tmp_path):
    repo = make_repo(tmp_path)

    assert "review" in denial(run_gate(repo, "git push -u origin feature"))


def test_denies_a_push_when_commits_landed_after_the_review(tmp_path):
    repo = make_repo(tmp_path)
    mark_reviewed(repo)
    git(repo, "commit", "--allow-empty", "-m", "after review")

    assert "review" in denial(run_gate(repo, "git push"))


@pytest.mark.parametrize("gh_output", ["1", ""], ids=["merged", "gh-failed"])
def test_denies_a_push_to_a_branch_whose_pr_is_merged(tmp_path, gh_output):
    repo = make_repo(tmp_path)
    mark_reviewed(repo)

    assert "merged" in denial(run_gate(repo, "git push", gh_output=gh_output))


@pytest.mark.parametrize(
    "command",
    [
        "git push -u origin feature",
        "git push -u origin feature  # then a PR to main",
        "git push -u origin feature  # then\ngh pr create --base main",
    ],
)
def test_stays_silent_on_a_reviewed_push_to_an_unmerged_branch(tmp_path, command):
    repo = make_repo(tmp_path)
    mark_reviewed(repo)

    assert denial(run_gate(repo, command, gh_output="0")) is None


def test_denies_when_the_gate_itself_fails(tmp_path):
    missing_project = tmp_path / "missing"  # running git there raises

    assert "failed" in denial(run_gate(missing_project, "git push"))
