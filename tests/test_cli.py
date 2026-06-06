from unittest.mock import Mock

import pytest

import cpt
from core import CptError
from tests.helpers import make_config, make_problem_payload


def args(**overrides):
    data = {
        "init": False,
        "config": False,
        "<key>": None,
        "<value>": None,
        "e": False,
        "--echo": False,
        "t": False,
        "--test": False,
        "g": False,
        "--gen": False,
    }
    data.update(overrides)
    return data


def run_main(monkeypatch, parsed_args):
    monkeypatch.setattr(cpt, "docopt", Mock(return_value=parsed_args))
    cpt.main()


def test_main_init_routes_to_run_init_without_loading_config(monkeypatch):
    run_init = Mock()
    load_config = Mock()
    monkeypatch.setattr(cpt, "run_init", run_init)
    monkeypatch.setattr(cpt, "load_config", load_config)

    run_main(monkeypatch, args(init=True))

    run_init.assert_called_once_with()
    load_config.assert_not_called()


def test_main_config_add_language_routes_to_add_language(monkeypatch):
    add_language = Mock()
    monkeypatch.setattr(cpt, "add_language", add_language)

    run_main(monkeypatch, args(config=True, **{"<key>": "add-language"}))

    add_language.assert_called_once_with()


def test_main_config_key_routes_to_print_config(monkeypatch):
    print_config = Mock()
    monkeypatch.setattr(cpt, "print_config", print_config)

    run_main(monkeypatch, args(config=True, **{"<key>": "languages.python"}))

    print_config.assert_called_once_with("languages.python")


def test_main_config_key_value_routes_to_set_config(monkeypatch):
    set_config = Mock()
    monkeypatch.setattr(cpt, "set_config", set_config)

    run_main(monkeypatch, args(config=True, **{"<key>": "language", "<value>": "cpp"}))

    set_config.assert_called_once_with("language", "cpp")


@pytest.mark.parametrize("flag", ["e", "--echo"])
def test_main_echo_routes_to_collect_batch_and_prints_payloads_without_loading_config(monkeypatch, capsys, flag):
    problem = make_problem_payload()
    load_config = Mock()
    monkeypatch.setattr(cpt, "load_config", load_config)
    monkeypatch.setattr(cpt, "collect_batch", Mock(return_value=[problem]))

    run_main(monkeypatch, args(**{flag: True}))

    assert str(problem) in capsys.readouterr().out
    load_config.assert_not_called()


@pytest.mark.parametrize("flag", ["t", "--test"])
def test_main_test_loads_config_and_calls_test(monkeypatch, flag, sample_config):
    test_command = Mock()
    monkeypatch.setattr(cpt, "load_config", Mock(return_value=sample_config))
    monkeypatch.setattr(cpt, "test", test_command)

    run_main(monkeypatch, args(**{flag: True}))

    test_command.assert_called_once_with(sample_config)


@pytest.mark.parametrize("flag", ["g", "--gen"])
def test_main_gen_loads_config_and_calls_gen(monkeypatch, flag, sample_config):
    gen = Mock()
    monkeypatch.setattr(cpt, "load_config", Mock(return_value=sample_config))
    monkeypatch.setattr(cpt, "gen", gen)

    run_main(monkeypatch, args(**{flag: True}))

    gen.assert_called_once_with(sample_config)


def test_main_default_loads_config_collects_batch_and_makes_each_problem(monkeypatch, sample_config):
    first = make_problem_payload(name="A")
    second = make_problem_payload(name="B")
    make_problem = Mock()
    monkeypatch.setattr(cpt, "load_config", Mock(return_value=sample_config))
    monkeypatch.setattr(cpt, "collect_batch", Mock(return_value=[first, second]))
    monkeypatch.setattr(cpt, "make_problem", make_problem)

    run_main(monkeypatch, args())

    assert make_problem.call_args_list == [
        ((first, sample_config),),
        ((second, sample_config),),
    ]


@pytest.mark.parametrize(
    ("error", "message", "code"),
    [
        (CptError("bad config"), "bad config", 1),
        (OSError("disk full"), "File system error: disk full", 1),
        (KeyboardInterrupt(), "Cancelled.", 130),
        (EOFError(), "Cancelled.", 130),
    ],
)
def test_main_user_actionable_errors_print_and_exit(monkeypatch, capsys, error, message, code):
    monkeypatch.setattr(cpt, "docopt", Mock(return_value=args()))
    monkeypatch.setattr(cpt, "load_config", Mock(side_effect=error))

    with pytest.raises(SystemExit) as exit_info:
        cpt.main()

    assert exit_info.value.code == code
    assert message in capsys.readouterr().out
