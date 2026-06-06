import pytest

from core import CptError, LanguageConfig, validate_config, validate_language_entry
from tests.helpers import make_config


def test_language_config_for_active_valid_python_config_returns_expected_fields(sample_config):
    language = LanguageConfig.for_active(sample_config)

    assert language.name == "python"
    assert language.source_file == "code.py"
    assert language.compile is None
    assert language.run == "python3 {source}"
    assert language.comment == "#"


def test_language_config_for_active_valid_cpp_config_returns_compile_run_executable_fields(sample_config):
    sample_config["language"] = "cpp"

    language = LanguageConfig.for_active(sample_config)

    assert language.name == "cpp"
    assert language.compile == "g++ {source} -o {executable}"
    assert language.run == "{executable}"
    assert language.executable == "code"
    assert language.comment == "//"


@pytest.mark.parametrize(
    ("extension", "expected_comment"),
    [(".py", "#"), (".cpp", "//")],
)
def test_language_config_for_active_missing_legacy_comment_defaults_by_extension(
    sample_config, extension, expected_comment
):
    sample_config["languages"]["python"].pop("comment")
    sample_config["languages"]["python"]["extension"] = extension

    language = LanguageConfig.for_active(sample_config)

    assert language.comment == expected_comment


def test_language_config_for_active_missing_active_language_raises_cpt_error(sample_config):
    sample_config["language"] = "rust"

    with pytest.raises(CptError, match="Active language"):
        LanguageConfig.for_active(sample_config)


@pytest.mark.parametrize(
    "entry",
    [
        {"source_file": "code.py", "run": "python3 {source}"},
        {
            "source_file": "code.cpp",
            "compile": "g++ {source} -o {executable}",
            "run": "{executable}",
            "executable": "code",
        },
    ],
)
def test_validate_language_entry_complete_language_passes(entry):
    validate_language_entry("lang", entry, require_complete=True)


def test_validate_language_entry_inactive_partial_language_passes_when_not_complete():
    validate_language_entry("draft", {"extension": ".zig"}, require_complete=False)


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ([], "must be an object"),
        ({"extension": 7}, "extension"),
        ({"source_file": 7}, "source_file"),
        ({"template": 7}, "template"),
        ({"compile": 7}, "compile"),
        ({"run": 7}, "run"),
        ({"executable": 7}, "executable"),
        ({"comment": 7}, "comment"),
        ({"run": "python3 {source}"}, "source_file"),
        ({"source_file": "code.py"}, "run"),
        ({"source_file": "code.cpp", "run": "{executable}", "compile": "g++"}, "executable"),
        ({"source_file": "/tmp/code.py", "run": "python3 {source}"}, "bare filename"),
        ({"source_file": "src/code.py", "run": "python3 {source}"}, "bare filename"),
        ({"source_file": "code.cpp", "run": "{executable}", "executable": "bin/code"}, "bare filename"),
        (
            {
                "source_file": "code",
                "compile": "g++ {source} -o {executable}",
                "run": "{executable}",
                "executable": "code",
            },
            "equal to 'source_file'",
        ),
    ],
)
def test_validate_language_entry_invalid_entry_raises_cpt_error(entry, message):
    with pytest.raises(CptError, match=message):
        validate_language_entry("bad", entry, require_complete=True)


def test_validate_config_complete_sample_config_passes(sample_config):
    validate_config(sample_config)


def test_validate_config_without_optional_editor_passes(sample_config):
    sample_config.pop("editor")

    validate_config(sample_config)


def test_validate_config_inactive_partial_language_passes_if_active_is_complete(sample_config):
    sample_config["languages"]["draft"] = {"extension": ".zig"}

    validate_config(sample_config)


def test_validate_config_unknown_top_level_keys_are_tolerated(sample_config):
    sample_config["custom"] = {"nested": True}

    validate_config(sample_config)


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ([], "top level"),
        ({}, "contests_path"),
        ({"contests_path": "/tmp"}, "language"),
        ({"contests_path": "/tmp", "language": "python"}, "languages"),
        (make_config("/tmp", contests_path=""), "contests_path"),
        (make_config("/tmp", contests_path="   "), "contests_path"),
        (make_config("/tmp", contests_path=7), "contests_path"),
        (make_config("/tmp", language=7), "language"),
        (make_config("/tmp", editor=7), "editor"),
        (make_config("/tmp", languages={}), "languages"),
        (make_config("/tmp", languages=[]), "languages"),
        (make_config("/tmp", languages={"python": []}), "language 'python'"),
        (make_config("/tmp", language="rust"), "active language"),
        (
            make_config("/tmp", languages={"python": {"source_file": "code.py"}}),
            "missing required field 'run'",
        ),
    ],
)
def test_validate_config_invalid_schema_raises_cpt_error(config, message):
    with pytest.raises(CptError, match=message) as error:
        validate_config(config)

    assert "config.json:" in str(error.value)
