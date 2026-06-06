import subprocess
from unittest.mock import Mock

import pytest

import cpt
from core import CptError, LanguageConfig
from tests.helpers import make_config, strip_ansi


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


def test_compile_solution_existing_executable_removes_before_compile(tmp_path, monkeypatch):
    language = make_language(
        name="cpp",
        source_file="code.cpp",
        compile="compile {source} {executable}",
        run="{executable}",
        executable="code",
        comment="//",
    )
    executable = tmp_path / "code"
    executable.write_text("stale")

    def run_checked(cmd, **kwargs):
        assert not executable.exists()
        executable.write_text("fresh")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(cpt, "run_checked", run_checked)

    assert cpt.compile_solution(language, tmp_path) is True
    assert executable.read_text() == "fresh"


@pytest.mark.parametrize(
    ("returncode", "create_executable"),
    [(1, True), (0, False)],
)
def test_compile_solution_compile_failure_prints_compilation_error(
    tmp_path, monkeypatch, capsys, returncode, create_executable
):
    language = make_language(
        name="cpp",
        source_file="code.cpp",
        compile="compile {source} {executable}",
        run="{executable}",
        executable="code",
        comment="//",
    )

    def run_checked(cmd, **kwargs):
        if create_executable:
            (tmp_path / "code").write_text("binary")
        return subprocess.CompletedProcess(cmd, returncode)

    monkeypatch.setattr(cpt, "run_checked", run_checked)

    assert cpt.compile_solution(language, tmp_path) is False
    assert "COMPILATION ERROR" in strip_ansi(capsys.readouterr().out)


def test_compile_solution_invalid_command_propagates_cpt_error(tmp_path):
    language = make_language(compile="{missing}", executable="code")

    with pytest.raises(CptError):
        cpt.compile_solution(language, tmp_path)


def test_resolve_run_command_compiled_language_substitutes_full_executable_path(tmp_path):
    language = make_language(compile="compile", run="{executable}", executable="code")

    command = cpt.resolve_run_command(language, tmp_path)

    assert command == [str(tmp_path / "code")]


def test_resolve_run_command_interpreted_language_substitutes_source_and_empty_executable(tmp_path):
    language = make_language(run="python3 {source} {executable}")

    command = cpt.resolve_run_command(language, tmp_path)

    assert command == ["python3", "code.py", ""]


def test_run_testcase_valid_input_passes_file_handle_pipes_and_cwd(tmp_path, monkeypatch):
    input_file = tmp_path / "in0.txt"
    input_file.write_text("1 2\n")
    completed = subprocess.CompletedProcess(["run"], 0)

    def run_checked(cmd, **kwargs):
        assert kwargs["stdin"].read() == "1 2\n"
        assert kwargs["stdout"] is subprocess.PIPE
        assert kwargs["stderr"] is subprocess.PIPE
        assert kwargs["cwd"] == tmp_path
        return completed

    monkeypatch.setattr(cpt, "run_checked", run_checked)

    assert cpt.run_testcase(["run"], input_file, tmp_path) is completed


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


def test_report_result_matching_output_prints_passed_message(tmp_path, capsys):
    input_file = tmp_path / "in0.txt"
    answer_file = tmp_path / "ans0.txt"
    input_file.write_text("1\n")
    answer_file.write_text("3\n")
    result = subprocess.CompletedProcess(["run"], 0, stdout=b"3\n\n", stderr=b"")

    cpt.report_result(0, result, input_file, answer_file)

    assert "Passed testcase #0" in strip_ansi(capsys.readouterr().out)


def test_report_result_wrong_answer_prints_input_expected_and_actual(tmp_path, capsys):
    input_file = tmp_path / "in0.txt"
    answer_file = tmp_path / "ans0.txt"
    input_file.write_text("1 2\n")
    answer_file.write_text("3\n")
    result = subprocess.CompletedProcess(["run"], 0, stdout=b"4\n", stderr=b"")

    cpt.report_result(0, result, input_file, answer_file)

    output = strip_ansi(capsys.readouterr().out)
    assert "WA on testcase #0" in output
    assert "Input:" in output
    assert "Expected:" in output
    assert "Your output:" in output
    assert "4" in output


def test_report_result_missing_answer_file_prints_skip_message(tmp_path, capsys):
    input_file = tmp_path / "in0.txt"
    input_file.write_text("1\n")
    result = subprocess.CompletedProcess(["run"], 0, stdout=b"3\n", stderr=b"")

    cpt.report_result(0, result, input_file, tmp_path / "ans0.txt")

    assert "No answer file for testcase #0" in strip_ansi(capsys.readouterr().out)


def test_report_result_runtime_error_prints_stdout_and_stderr(tmp_path, capsys):
    input_file = tmp_path / "in0.txt"
    answer_file = tmp_path / "ans0.txt"
    input_file.write_text("1\n")
    answer_file.write_text("3\n")
    result = subprocess.CompletedProcess(["run"], 1, stdout=b"partial\n", stderr=b"boom\n")

    cpt.report_result(0, result, input_file, answer_file)

    output = strip_ansi(capsys.readouterr().out)
    assert "Runtime error on testcase #0" in output
    assert "Stdout:" in output
    assert "partial" in output
    assert "Stderr:" in output
    assert "boom" in output


def test_report_result_undecodable_runtime_output_does_not_crash(tmp_path, capsys):
    input_file = tmp_path / "in0.txt"
    answer_file = tmp_path / "ans0.txt"
    input_file.write_text("1\n")
    answer_file.write_text("3\n")
    result = subprocess.CompletedProcess(["run"], 1, stdout=b"\xff", stderr=b"")

    cpt.report_result(0, result, input_file, answer_file)

    assert "Runtime error on testcase #0" in strip_ansi(capsys.readouterr().out)


def test_test_compiled_language_compile_failure_stops_before_reporting(tmp_path, monkeypatch):
    config = make_config(tmp_path, language="cpp")
    monkeypatch.chdir(tmp_path)
    compiled = Mock(return_value=False)
    reported = Mock()
    monkeypatch.setattr(cpt, "compile_solution", compiled)
    monkeypatch.setattr(cpt, "report_result", reported)

    cpt.test(config)

    compiled.assert_called_once()
    reported.assert_not_called()


def test_test_compiled_language_compile_success_runs_contiguous_testcases(tmp_path, monkeypatch):
    config = make_config(tmp_path, language="cpp")
    (tmp_path / "in0.txt").write_text("0")
    (tmp_path / "in1.txt").write_text("1")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cpt, "compile_solution", Mock(return_value=True))
    monkeypatch.setattr(cpt, "resolve_run_command", Mock(return_value=["run"]))
    monkeypatch.setattr(
        cpt,
        "run_testcase",
        Mock(return_value=subprocess.CompletedProcess(["run"], 0, stdout=b"", stderr=b"")),
    )
    reported = Mock()
    monkeypatch.setattr(cpt, "report_result", reported)

    cpt.test(config)

    assert reported.call_count == 2


def test_test_interpreted_language_missing_middle_input_stops_at_gap(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    (tmp_path / "in0.txt").write_text("0")
    (tmp_path / "in2.txt").write_text("2")
    monkeypatch.chdir(tmp_path)
    compiled = Mock()
    monkeypatch.setattr(cpt, "compile_solution", compiled)
    monkeypatch.setattr(cpt, "resolve_run_command", Mock(return_value=["run"]))
    monkeypatch.setattr(
        cpt,
        "run_testcase",
        Mock(return_value=subprocess.CompletedProcess(["run"], 0, stdout=b"", stderr=b"")),
    )
    reported = Mock()
    monkeypatch.setattr(cpt, "report_result", reported)

    cpt.test(config)

    compiled.assert_not_called()
    assert reported.call_count == 1


def test_test_directory_without_in0_prints_no_testcases_message(tmp_path, monkeypatch, capsys):
    config = make_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cpt, "resolve_run_command", Mock(return_value=["run"]))

    cpt.test(config)

    assert "No testcases found" in strip_ansi(capsys.readouterr().out)


def test_test_runtime_error_on_first_case_still_reports_next_case(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    (tmp_path / "in0.txt").write_text("0")
    (tmp_path / "in1.txt").write_text("1")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cpt, "resolve_run_command", Mock(return_value=["run"]))
    monkeypatch.setattr(
        cpt,
        "run_testcase",
        Mock(side_effect=[
            subprocess.CompletedProcess(["run"], 1, stdout=b"", stderr=b"err"),
            subprocess.CompletedProcess(["run"], 0, stdout=b"", stderr=b""),
        ]),
    )
    reported = Mock()
    monkeypatch.setattr(cpt, "report_result", reported)

    cpt.test(config)

    assert reported.call_count == 2
