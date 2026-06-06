import subprocess
from unittest.mock import Mock

import pytest

import cpt
from core import CptError, LanguageConfig


def make_language(**overrides):
    data = {
        "name": "python",
        "extension": ".py",
        "source_file": "code.py",
        "template": None,
        "compile": None,
        "run": "python3 {source}",
        "executable": None,
        "comment": "#",
    }
    data.update(overrides)
    return LanguageConfig(**data)


@pytest.mark.parametrize(
    ("template", "subs", "expected"),
    [
        ("python3 {source}", {"source": "code.py", "executable": ""}, ["python3", "code.py"]),
        (
            '"{executable}" --input "{source}"',
            {"executable": "/tmp/problem dir/code", "source": "code file.py"},
            ["/tmp/problem dir/code", "--input", "code file.py"],
        ),
        (
            "g++ -std=c++17 {source} -o {executable}",
            {"source": "code.cpp", "executable": "code"},
            ["g++", "-std=c++17", "code.cpp", "-o", "code"],
        ),
    ],
)
def test_build_command_valid_templates_substitute_and_tokenize(template, subs, expected):
    command = cpt.build_command(template, **subs)

    assert command == expected


@pytest.mark.parametrize("template", ["", "   "])
def test_build_command_empty_template_raises_cpt_error(template):
    with pytest.raises(CptError, match="empty"):
        cpt.build_command(template, source="code.py", executable="")


@pytest.mark.parametrize("template", ['"unterminated', "{unknown}", "{source"])
def test_build_command_invalid_template_raises_cpt_error(template):
    with pytest.raises(CptError):
        cpt.build_command(template, source="code.py", executable="")


def test_run_checked_success_returns_completed_process(monkeypatch):
    completed = subprocess.CompletedProcess(["true"], 0)
    run_checked = Mock(return_value=completed)
    monkeypatch.setattr(cpt.subprocess, "run", run_checked)

    result = cpt.run_checked(["true"], cwd="/tmp")

    assert result is completed
    run_checked.assert_called_once_with(["true"], cwd="/tmp")


def test_run_checked_missing_command_raises_cpt_error(monkeypatch):
    monkeypatch.setattr(cpt.subprocess, "run", Mock(side_effect=FileNotFoundError()))

    with pytest.raises(CptError, match="Command not found"):
        cpt.run_checked(["missing"])


def test_run_checked_os_error_raises_cpt_error(monkeypatch):
    monkeypatch.setattr(cpt.subprocess, "run", Mock(side_effect=OSError("no exec")))

    with pytest.raises(CptError, match="Could not run"):
        cpt.run_checked(["bad"])


def test_resolve_run_command_compiled_language_substitutes_full_executable_path(tmp_path):
    language = make_language(compile="compile", run="{executable}", executable="code")

    command = cpt.resolve_run_command(language, tmp_path)

    assert command == [str(tmp_path / "code")]


def test_resolve_run_command_interpreted_language_substitutes_source_and_empty_executable(tmp_path):
    language = make_language(run="python3 {source} {executable}")

    command = cpt.resolve_run_command(language, tmp_path)

    assert command == ["python3", "code.py", ""]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("  a  \n b \n", ["a", "b"]),
        ("a\n\n", ["a"]),
        ("a\n\nb\n", ["a", "", "b"]),
        ("", []),
        ("   \n\t\n", []),
    ],
)
def test_normalize_lines_strips_lines_and_drops_trailing_blanks(text, expected):
    assert cpt._normalize_lines(text) == expected
