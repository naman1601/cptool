import json
from unittest.mock import Mock

import pytest

import config
from core import CptError
from tests.helpers import make_config, write_json


def set_inputs(monkeypatch, values):
    iterator = iter(values)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(iterator))


def test_load_config_missing_file_raises_cpt_error(config_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    with pytest.raises(CptError, match="Config not found"):
        config.load_config()


def test_load_config_invalid_json_raises_cpt_error(config_path, monkeypatch):
    config_path.write_text("{")
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    with pytest.raises(CptError, match="not valid JSON"):
        config.load_config()


def test_load_config_schema_invalid_json_raises_cpt_error(config_path, monkeypatch):
    write_json(config_path, {"contests_path": ""})
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    with pytest.raises(CptError, match="config.json:"):
        config.load_config()


def test_load_config_valid_json_returns_parsed_dict(config_path, monkeypatch, sample_config):
    write_json(config_path, sample_config)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    assert config.load_config() == sample_config


def test_save_config_writes_indented_json(config_path, monkeypatch, sample_config):
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    config.save_config(sample_config)

    assert json.loads(config_path.read_text()) == sample_config
    assert "\n  " in config_path.read_text()


def test_print_config_without_key_prints_full_config(monkeypatch, capsys, sample_config):
    monkeypatch.setattr(config, "load_config", Mock(return_value=sample_config))

    config.print_config()

    assert json.loads(capsys.readouterr().out) == sample_config


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("language", "python"),
        ("languages.python.run", "python3 {source}"),
        ("languages.python", None),
    ],
)
def test_print_config_dotted_key_prints_json_value(monkeypatch, capsys, sample_config, key, expected):
    monkeypatch.setattr(config, "load_config", Mock(return_value=sample_config))

    config.print_config(key)

    printed = json.loads(capsys.readouterr().out)
    assert printed == (sample_config["languages"]["python"] if expected is None else expected)


@pytest.mark.parametrize("key", ["missing", "language.name"])
def test_print_config_missing_or_scalar_path_raises_cpt_error(monkeypatch, sample_config, key):
    monkeypatch.setattr(config, "load_config", Mock(return_value=sample_config))

    with pytest.raises(CptError, match="not found"):
        config.print_config(key)


def test_set_config_string_field_updates_and_saves(config_path, monkeypatch, sample_config):
    write_json(config_path, sample_config)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    config.set_config("language", "cpp")

    assert json.loads(config_path.read_text())["language"] == "cpp"


def test_set_config_previous_null_optional_language_field_stores_string(config_path, monkeypatch, sample_config):
    write_json(config_path, sample_config)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    config.set_config("languages.python.template", "/tmp/template.py")

    assert json.loads(config_path.read_text())["languages"]["python"]["template"] == "/tmp/template.py"


def test_set_config_existing_integer_field_coerces_to_int(config_path, monkeypatch, sample_config):
    sample_config["retries"] = 1
    write_json(config_path, sample_config)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    config.set_config("retries", "7")

    assert json.loads(config_path.read_text())["retries"] == 7


@pytest.mark.parametrize(("value", "expected"), [("true", True), ("1", True), ("yes", True), ("no", False)])
def test_set_config_existing_boolean_field_coerces_from_string(config_path, monkeypatch, sample_config, value, expected):
    sample_config["enabled"] = False
    write_json(config_path, sample_config)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    config.set_config("enabled", value)

    assert json.loads(config_path.read_text())["enabled"] is expected


@pytest.mark.parametrize("key", ["missing.child", "languages.python.missing"])
def test_set_config_missing_key_raises_cpt_error(config_path, monkeypatch, sample_config, key):
    write_json(config_path, sample_config)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    with pytest.raises(CptError, match="not found"):
        config.set_config(key, "value")


def test_set_config_missing_leaf_mentions_add_language(config_path, monkeypatch, sample_config):
    write_json(config_path, sample_config)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    with pytest.raises(CptError, match="config add-language"):
        config.set_config("languages.python.missing", "value")


def test_set_config_invalid_integer_string_raises_cpt_error(config_path, monkeypatch, sample_config):
    sample_config["retries"] = 1
    write_json(config_path, sample_config)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    with pytest.raises(CptError, match="valid integer"):
        config.set_config("retries", "abc")


@pytest.mark.parametrize("key", ["languages.python.run", "editor"])
def test_set_config_null_that_violates_schema_raises_and_does_not_save(config_path, monkeypatch, sample_config, key):
    write_json(config_path, sample_config)
    before = config_path.read_text()
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    with pytest.raises(CptError):
        config.set_config(key, "null")

    assert config_path.read_text() == before


def test_add_language_adds_interpreted_language_with_empty_template(
    config_path, templates_dir, monkeypatch, sample_config
):
    write_json(config_path, sample_config)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "TEMPLATES_DIR", templates_dir)
    set_inputs(monkeypatch, ["ruby", ".rb", "", "", "", "ruby {source}", "#", ""])

    config.add_language()

    saved = json.loads(config_path.read_text())
    assert saved["languages"]["ruby"]["source_file"] == "code.rb"
    assert saved["languages"]["ruby"]["run"] == "ruby {source}"
    assert (templates_dir / "template.rb").read_text() == ""


def test_add_language_adds_compiled_language_and_copies_template(
    config_path, templates_dir, tmp_path, monkeypatch, sample_config
):
    template_source = tmp_path / "main.rs"
    template_source.write_text("fn main() {}\n")
    write_json(config_path, sample_config)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "TEMPLATES_DIR", templates_dir)
    set_inputs(
        monkeypatch,
        ["rust", ".rs", "", "rustc {source} -o {executable}", "main", "{executable}", "//", str(template_source)],
    )

    config.add_language()

    saved = json.loads(config_path.read_text())
    assert saved["languages"]["rust"]["executable"] == "main"
    assert (templates_dir / "template.rs").read_text() == "fn main() {}\n"


@pytest.mark.parametrize(("answer", "expected_run"), [("n", "python3 {source}"), ("y", "ruby {source}")])
def test_add_language_overwrites_existing_language_only_on_exact_y(
    config_path, templates_dir, monkeypatch, sample_config, answer, expected_run
):
    write_json(config_path, sample_config)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "TEMPLATES_DIR", templates_dir)
    values = ["python", answer]
    if answer == "y":
        values.extend([".py", "", "", "", "ruby {source}", "#", ""])
    set_inputs(monkeypatch, values)

    config.add_language()

    assert json.loads(config_path.read_text())["languages"]["python"]["run"] == expected_run


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ([""], "cannot be empty"),
        (["ruby", "rb"], "Extension must start"),
        (["ruby", "./bad"], "path separators"),
        (["ruby", ".rb", "", "", "", ""], "Run command cannot be empty"),
    ],
)
def test_add_language_early_return_does_not_save(config_path, templates_dir, monkeypatch, capsys, sample_config, inputs, message):
    write_json(config_path, sample_config)
    before = config_path.read_text()
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "TEMPLATES_DIR", templates_dir)
    set_inputs(monkeypatch, inputs)

    config.add_language()

    assert message in capsys.readouterr().out
    assert config_path.read_text() == before


def test_add_language_template_source_missing_does_not_save(config_path, templates_dir, monkeypatch, capsys, sample_config):
    write_json(config_path, sample_config)
    before = config_path.read_text()
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "TEMPLATES_DIR", templates_dir)
    set_inputs(monkeypatch, ["ruby", ".rb", "", "", "", "ruby {source}", "#", str(templates_dir / "missing.rb")])

    config.add_language()

    assert "File not found" in capsys.readouterr().out
    assert config_path.read_text() == before


def test_add_language_compile_without_executable_raises_without_writing_template_or_config(
    config_path, templates_dir, monkeypatch, sample_config
):
    write_json(config_path, sample_config)
    before = config_path.read_text()
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "TEMPLATES_DIR", templates_dir)
    set_inputs(monkeypatch, ["rust", ".rs", "", "rustc {source}", "", "{executable}", "//", ""])

    with pytest.raises(CptError, match="compile"):
        config.add_language()

    assert config_path.read_text() == before
    assert not (templates_dir / "template.rs").exists()


def test_run_init_fresh_blank_inputs_writes_valid_default_config_and_seeds_templates(
    config_path, templates_dir, tmp_path, monkeypatch
):
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "TEMPLATES_DIR", templates_dir)
    monkeypatch.setattr(config, "CPTOOL_DIR", tmp_path)
    monkeypatch.setattr(config, "available_editors", Mock(return_value=[]))
    seeded = Mock()
    monkeypatch.setattr(config, "seed_templates", seeded)
    set_inputs(monkeypatch, ["", "", ""])

    config.run_init()

    saved = json.loads(config_path.read_text())
    assert saved["language"] == "cpp"
    assert saved["editor"] == ""
    assert saved["contests_path"] == str((tmp_path / "contests").resolve())
    seeded.assert_called_once_with()


def test_run_init_uses_detected_editor_as_blank_default(config_path, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "CPTOOL_DIR", tmp_path)
    monkeypatch.setattr(config, "available_editors", Mock(return_value=["vim"]))
    monkeypatch.setattr(config, "seed_templates", Mock())
    set_inputs(monkeypatch, ["", "python", ""])

    config.run_init()

    assert json.loads(config_path.read_text())["editor"] == "vim"


@pytest.mark.parametrize(("overwrite", "expected_language"), [("n", "python"), ("y", "cpp")])
def test_run_init_existing_config_overwrite_choice_controls_replacement(
    config_path, tmp_path, monkeypatch, sample_config, overwrite, expected_language
):
    sample_config["language"] = "python"
    write_json(config_path, sample_config)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "CPTOOL_DIR", tmp_path)
    monkeypatch.setattr(config, "available_editors", Mock(return_value=[]))
    monkeypatch.setattr(config, "seed_templates", Mock())
    inputs = [overwrite]
    if overwrite == "y":
        inputs.extend(["", "", ""])
    set_inputs(monkeypatch, inputs)

    config.run_init()

    assert json.loads(config_path.read_text())["language"] == expected_language


def test_run_init_unknown_requested_language_raises_and_does_not_save(config_path, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "CPTOOL_DIR", tmp_path)
    monkeypatch.setattr(config, "available_editors", Mock(return_value=[]))
    seeded = Mock()
    monkeypatch.setattr(config, "seed_templates", seeded)
    set_inputs(monkeypatch, ["", "rust", ""])

    with pytest.raises(CptError, match="Unknown language"):
        config.run_init()

    assert not config_path.exists()
    seeded.assert_not_called()
