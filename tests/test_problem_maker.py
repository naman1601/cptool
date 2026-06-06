from unittest.mock import Mock

import pytest

import oj_handlers
import problem_maker
from core import CptError, LanguageConfig
from tests.helpers import make_config, make_problem_payload, strip_ansi


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


def test_seed_templates_copies_defaults_without_overwriting_user_templates(templates_dir, monkeypatch):
    (templates_dir / "default.cpp").write_text("default cpp")
    (templates_dir / "default.py").write_text("default py")
    (templates_dir / "default").write_text("ignored")
    (templates_dir / "template.cpp").write_text("user cpp")
    monkeypatch.setattr(problem_maker, "TEMPLATES_DIR", templates_dir)

    problem_maker.seed_templates()

    assert (templates_dir / "template.cpp").read_text() == "user cpp"
    assert (templates_dir / "template.py").read_text() == "default py"
    assert not (templates_dir / "template").exists()


def test_resolve_target_path_known_platform_returns_platform_path(contests_dir, sample_problem):
    path = problem_maker._resolve_target_path(sample_problem, contests_dir)

    assert path == contests_dir / "codeforces/999/a"


def test_resolve_target_path_unknown_platform_returns_unknown_path_and_prints_warning(contests_dir, capsys):
    problem = make_problem_payload(group="Kattis", name="Hello World")

    path = problem_maker._resolve_target_path(problem, contests_dir)

    assert path == contests_dir / "unknown/Hello_World"
    assert "unknown OJ" in capsys.readouterr().out


def test_resolve_target_path_platform_escape_raises_cpt_error(contests_dir, monkeypatch):
    class EscapingPlatform:
        def get_path(self, json_data, contests_path):
            return contests_path.parent / "outside"

    monkeypatch.setattr(oj_handlers, "detect", Mock(return_value=EscapingPlatform()))

    with pytest.raises(CptError, match="outside the contests directory"):
        problem_maker._resolve_target_path(make_problem_payload(), contests_dir)


def test_create_code_file_writes_metadata_and_template_content(tmp_path):
    template = tmp_path / "template.py"
    template.write_text("print('ready')\n")
    language = make_language(template=str(template), comment="#")
    code_file = tmp_path / "nested" / "code.py"

    problem_maker._create_code_file(code_file, language, make_problem_payload())

    content = code_file.read_text()
    assert content.startswith(
        "# url: https://codeforces.com/contest/999/problem/A\n"
        "# time limit: 2s\n"
        "# memory limit: 256MB\n"
    )
    assert content.endswith("print('ready')\n")


@pytest.mark.parametrize("template", [None, "/missing/template.py"])
def test_create_code_file_uses_header_only_when_template_missing(tmp_path, template):
    language = make_language(template=template, comment="//")
    code_file = tmp_path / "code.py"
    problem = make_problem_payload(timeLimit=None, memoryLimit=None)
    problem.pop("timeLimit")
    problem.pop("memoryLimit")

    problem_maker._create_code_file(code_file, language, problem)

    assert code_file.read_text() == (
        "// url: https://codeforces.com/contest/999/problem/A\n"
        "// time limit: ?s\n"
        "// memory limit: ?MB\n"
    )


def test_write_testcases_writes_files_in_order_and_removes_stale_files(tmp_path):
    (tmp_path / "in9.txt").write_text("stale")
    (tmp_path / "ans9.txt").write_text("stale")
    tests = [{"input": "a", "output": "b"}, {"input": "c", "output": "d"}]

    problem_maker._write_testcases(tmp_path, tests)

    assert (tmp_path / "in0.txt").read_text() == "a"
    assert (tmp_path / "ans0.txt").read_text() == "b"
    assert (tmp_path / "in1.txt").read_text() == "c"
    assert (tmp_path / "ans1.txt").read_text() == "d"
    assert not (tmp_path / "in9.txt").exists()
    assert not (tmp_path / "ans9.txt").exists()


def test_write_testcases_empty_list_removes_stale_files(tmp_path):
    (tmp_path / "in0.txt").write_text("stale")
    (tmp_path / "ans0.txt").write_text("stale")

    problem_maker._write_testcases(tmp_path, [])

    assert not (tmp_path / "in0.txt").exists()
    assert not (tmp_path / "ans0.txt").exists()


@pytest.mark.parametrize(
    ("tests", "message"),
    [
        ({}, "not a list"),
        ([[]], "missing 'input' or 'output'"),
        ([{"output": ""}], "missing 'input' or 'output'"),
        ([{"input": ""}], "missing 'input' or 'output'"),
        ([{"input": 1, "output": ""}], "non-string"),
        ([{"input": "", "output": 1}], "non-string"),
    ],
)
def test_write_testcases_malformed_tests_raise_without_removing_stale_files(tmp_path, tests, message):
    (tmp_path / "in0.txt").write_text("stale")

    with pytest.raises(CptError, match=message):
        problem_maker._write_testcases(tmp_path, tests)

    assert (tmp_path / "in0.txt").read_text() == "stale"


def test_make_problem_new_codeforces_problem_creates_files_and_opens_editor(
    contests_dir, tmp_path, monkeypatch, capsys
):
    template = tmp_path / "template.py"
    template.write_text("print(input())\n")
    config = make_config(contests_dir, editor="code")
    config["languages"]["python"]["template"] = str(template)
    opened_editor = Mock()
    monkeypatch.setattr(problem_maker, "open_in_editor", opened_editor)

    problem_maker.make_problem(make_problem_payload(), config)

    target = contests_dir / "codeforces/999/a"
    assert (target / "code.py").read_text().endswith("print(input())\n")
    assert (target / "in0.txt").read_text() == "1 2\n"
    assert (target / "ans1.txt").read_text() == "30\n"
    assert "Problem ready:" in capsys.readouterr().out
    opened_editor.assert_called_once_with("code", target / "code.py")


def test_make_problem_existing_code_file_is_not_overwritten_but_testcases_refresh(contests_dir, monkeypatch):
    target = contests_dir / "codeforces/999/a"
    target.mkdir(parents=True)
    (target / "code.py").write_text("custom")
    (target / "in9.txt").write_text("stale")
    monkeypatch.setattr(problem_maker, "open_in_editor", Mock())

    problem_maker.make_problem(make_problem_payload(tests=[{"input": "new", "output": "out"}]), make_config(contests_dir))

    assert (target / "code.py").read_text() == "custom"
    assert (target / "in0.txt").read_text() == "new"
    assert not (target / "in9.txt").exists()


def test_make_problem_unknown_oj_creates_under_unknown_and_prints_warning(contests_dir, monkeypatch, capsys):
    monkeypatch.setattr(problem_maker, "open_in_editor", Mock())

    problem_maker.make_problem(make_problem_payload(group="Kattis", name="Hello World"), make_config(contests_dir))

    assert (contests_dir / "unknown/Hello_World/code.py").is_file()
    assert "unknown OJ" in capsys.readouterr().out


def test_make_problem_missing_active_language_raises_before_creating_problem_dir(contests_dir):
    config = make_config(contests_dir, language="rust")

    with pytest.raises(CptError, match="Active language"):
        problem_maker.make_problem(make_problem_payload(), config)

    assert not any(contests_dir.iterdir())


def test_make_problem_malformed_tests_leaves_code_file_but_writes_no_partial_testcases(contests_dir, monkeypatch):
    monkeypatch.setattr(problem_maker, "open_in_editor", Mock())

    with pytest.raises(CptError, match="missing"):
        problem_maker.make_problem(make_problem_payload(tests=[{"input": "x"}]), make_config(contests_dir))

    target = contests_dir / "codeforces/999/a"
    assert (target / "code.py").is_file()
    assert not list(target.glob("in*.txt"))
    assert not list(target.glob("ans*.txt"))


def test_gen_missing_source_and_existing_template_copies_template(tmp_path, monkeypatch):
    template = tmp_path / "template.py"
    template.write_text("print('template')\n")
    config = make_config(tmp_path)
    config["languages"]["python"]["template"] = str(template)
    monkeypatch.chdir(tmp_path)

    problem_maker.gen(config)

    assert (tmp_path / "code.py").read_text() == "print('template')\n"


def test_gen_missing_source_and_missing_template_creates_empty_source(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config["languages"]["python"]["template"] = str(tmp_path / "missing.py")
    monkeypatch.chdir(tmp_path)

    problem_maker.gen(config)

    assert (tmp_path / "code.py").read_text() == ""


@pytest.mark.parametrize(("answer", "expected"), [("n", "custom"), ("y", "template"), ("yes", "custom")])
def test_gen_existing_source_overwrites_only_on_exact_y(tmp_path, monkeypatch, answer, expected):
    template = tmp_path / "template.py"
    template.write_text("template")
    (tmp_path / "code.py").write_text("custom")
    config = make_config(tmp_path)
    config["languages"]["python"]["template"] = str(template)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", Mock(return_value=answer))

    problem_maker.gen(config)

    assert (tmp_path / "code.py").read_text() == expected
