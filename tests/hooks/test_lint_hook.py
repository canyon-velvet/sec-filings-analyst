import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).parents[2] / ".claude" / "hooks" / "lint.py"
REAL_RUFF = Path(sys.executable).parent / "ruff"


def make_project(tmp_path):
    """A project dir whose .venv has ruff, like the real one after `uv sync`."""
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "ruff").symlink_to(REAL_RUFF)
    return tmp_path


def run_hook(project, file_path):
    payload = {
        "hook_event_name": "PostToolUse",
        "cwd": str(project),
        "tool_name": "Edit",
        "tool_input": {"file_path": str(file_path)},
    }
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(project), "PATH": "/usr/bin:/bin"},
    )


def test_formats_the_edited_python_file(tmp_path):
    project = make_project(tmp_path)
    edited = project / "mod.py"
    edited.write_text("x=1\n")

    result = run_hook(project, edited)

    assert result.returncode == 0
    assert result.stdout == ""
    assert edited.read_text() == "x = 1\n"


def test_auto_fixes_fixable_lint_errors(tmp_path):
    project = make_project(tmp_path)
    edited = project / "mod.py"
    edited.write_text('x = f"a"\n')

    result = run_hook(project, edited)

    assert result.returncode == 0
    assert result.stdout == ""
    assert edited.read_text() == 'x = "a"\n'


def test_feeds_unfixable_errors_back_to_claude_as_a_block(tmp_path):
    project = make_project(tmp_path)
    edited = project / "mod.py"
    edited.write_text("print(undefined_name)\n")

    result = run_hook(project, edited)

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["decision"] == "block"
    assert "F821" in output["reason"]


def test_ignores_non_python_files(tmp_path):
    project = make_project(tmp_path)
    edited = project / "Makefile"
    edited.write_text("x=1\n")

    result = run_hook(project, edited)

    assert result.returncode == 0
    assert result.stdout == ""
    assert edited.read_text() == "x=1\n"


def test_does_nothing_before_the_project_exists(tmp_path):
    edited = tmp_path / "mod.py"
    edited.write_text("x=1\n")

    result = run_hook(tmp_path, edited)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert edited.read_text() == "x=1\n"


def test_does_not_block_on_errors_the_formatter_fixes(tmp_path):
    project = make_project(tmp_path)
    (project / "pyproject.toml").write_text('[tool.ruff.lint]\nextend-select = ["E501"]\n')
    edited = project / "mod.py"
    edited.write_text("x = {" + ", ".join(f'"key{i}": {i}' for i in range(12)) + "}\n")

    result = run_hook(project, edited)

    assert result.returncode == 0
    assert result.stdout == ""


def test_explains_why_when_ruff_itself_fails(tmp_path):
    project = make_project(tmp_path)
    (project / "pyproject.toml").write_text('[tool.ruff]\nline-length = "wide"\n')
    edited = project / "mod.py"
    edited.write_text("x = 1\n")

    result = run_hook(project, edited)

    assert result.returncode == 0
    assert "line-length" in json.loads(result.stdout)["reason"]


def test_ignores_files_outside_the_project(tmp_path):
    project = make_project(tmp_path / "project")
    edited = tmp_path / "elsewhere.py"
    edited.write_text("import os\nx=1\n")

    result = run_hook(project, edited)

    assert result.stdout == ""
    assert edited.read_text() == "import os\nx=1\n"


def test_leaves_files_excluded_by_ruff_config_alone(tmp_path):
    project = make_project(tmp_path)
    (project / "pyproject.toml").write_text('[tool.ruff]\nextend-exclude = ["vendor"]\n')
    (project / "vendor").mkdir()
    edited = project / "vendor" / "lib.py"
    edited.write_text("import os\nx=1\n")

    result = run_hook(project, edited)

    assert result.stdout == ""
    assert edited.read_text() == "import os\nx=1\n"


def test_keeps_an_import_claude_has_not_used_yet_but_reports_it(tmp_path):
    project = make_project(tmp_path)
    edited = project / "mod.py"
    edited.write_text("import json\n")

    result = run_hook(project, edited)

    assert result.returncode == 0
    assert "F401" in json.loads(result.stdout)["reason"]
    assert edited.read_text() == "import json\n"


def test_reports_an_import_its_own_fixes_left_unused(tmp_path):
    project = make_project(tmp_path)
    (project / "pyproject.toml").write_text(
        '[tool.ruff]\ntarget-version = "py312"\n[tool.ruff.lint]\nextend-select = ["UP"]\n'
    )
    edited = project / "mod.py"
    edited.write_text("from typing import Optional\n\nx: Optional[int] = None\n")

    result = run_hook(project, edited)

    assert json.loads(result.stdout)["decision"] == "block"
    assert "F401" in json.loads(result.stdout)["reason"]
