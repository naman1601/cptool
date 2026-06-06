from unittest.mock import Mock

import pytest

import companion_listener
from core import CptError
from tests.helpers import make_problem_payload


class FakeServer:
    def __init__(self, events):
        self.events = list(events)
        self.timeout = None
        self.received = None
        self.timed_out = False

    def handle_request(self):
        event = self.events.pop(0)
        if event == "timeout":
            self.timed_out = True
        elif event == "rejected":
            self.received = None
            self.timed_out = False
        else:
            self.received = event
            self.timed_out = False


def test_validate_complete_payload_passes(sample_problem):
    companion_listener._validate(sample_problem)


@pytest.mark.parametrize("field", companion_listener.REQUIRED_FIELDS)
def test_validate_missing_required_field_raises_cpt_error(sample_problem, field):
    sample_problem.pop(field)

    with pytest.raises(CptError, match="missing field"):
        companion_listener._validate(sample_problem)


@pytest.mark.parametrize("field", ["name", "group", "url"])
@pytest.mark.parametrize("value", ["", "   ", 7])
def test_validate_empty_or_non_string_text_field_raises_cpt_error(sample_problem, field, value):
    sample_problem[field] = value

    with pytest.raises(CptError, match=field):
        companion_listener._validate(sample_problem)


@pytest.mark.parametrize(
    "batch",
    [
        [],
        {},
        {"size": 0},
        {"size": -1},
        {"size": True},
        {"size": "1"},
    ],
)
def test_validate_malformed_batch_raises_cpt_error(sample_problem, batch):
    sample_problem["batch"] = batch

    with pytest.raises(CptError, match="malformed 'batch'"):
        companion_listener._validate(sample_problem)


def test_receive_returns_received_problem(sample_problem):
    server = FakeServer([sample_problem])

    assert companion_listener._receive(server, timeout=1.5) is sample_problem
    assert server.timeout == 1.5


def test_receive_timeout_returns_none():
    server = FakeServer(["timeout"])

    assert companion_listener._receive(server, timeout=0.1) is None


def test_receive_rejected_request_loops_until_later_valid_problem(sample_problem):
    server = FakeServer(["rejected", sample_problem])

    assert companion_listener._receive(server, timeout=1.0) is sample_problem


class ServerFactory:
    def __init__(self):
        self.server = Mock()

    def __call__(self, address, handler):
        self.address = address
        self.handler = handler
        return self.server


def test_collect_batch_single_problem_returns_first_problem_and_closes_server(monkeypatch, sample_problem):
    factory = ServerFactory()
    monkeypatch.setattr(companion_listener, "_CompanionServer", factory)
    monkeypatch.setattr(companion_listener, "_receive", Mock(return_value=sample_problem))

    problems = companion_listener.collect_batch()

    assert problems == [sample_problem]
    factory.server.server_close.assert_called_once_with()


def test_collect_batch_complete_multi_problem_batch_returns_same_id_problems(monkeypatch):
    first = make_problem_payload(name="A", batch={"id": "batch", "size": 2})
    second = make_problem_payload(name="B", batch={"id": "batch", "size": 2})
    factory = ServerFactory()
    monkeypatch.setattr(companion_listener, "_CompanionServer", factory)
    monkeypatch.setattr(companion_listener, "_receive", Mock(side_effect=[first, second]))
    monkeypatch.setattr(companion_listener.time, "monotonic", Mock(side_effect=[0.0, 1.0]))

    assert companion_listener.collect_batch() == [first, second]


def test_collect_batch_wrong_batch_id_is_ignored_and_warning_is_printed(monkeypatch, capsys):
    first = make_problem_payload(name="A", batch={"id": "batch", "size": 2})
    wrong = make_problem_payload(name="X", batch={"id": "other", "size": 1})
    second = make_problem_payload(name="B", batch={"id": "batch", "size": 2})
    factory = ServerFactory()
    monkeypatch.setattr(companion_listener, "_CompanionServer", factory)
    monkeypatch.setattr(companion_listener, "_receive", Mock(side_effect=[first, wrong, second]))
    monkeypatch.setattr(companion_listener.time, "monotonic", Mock(side_effect=[0.0, 1.0, 2.0]))

    problems = companion_listener.collect_batch()

    assert problems == [first, second]
    assert "different batch" in capsys.readouterr().err


def test_collect_batch_wrong_batch_id_does_not_reset_batch_timeout(monkeypatch, capsys):
    first = make_problem_payload(name="A", batch={"id": "batch", "size": 3})
    wrong = make_problem_payload(name="X", batch={"id": "other", "size": 3})
    factory = ServerFactory()
    receive = Mock(side_effect=[first, wrong, None])
    monkeypatch.setattr(companion_listener, "_CompanionServer", factory)
    monkeypatch.setattr(companion_listener, "_receive", receive)
    monkeypatch.setattr(companion_listener.time, "monotonic", Mock(side_effect=[100.0, 101.0, 109.0]))

    problems = companion_listener.collect_batch()

    assert problems == [first]
    assert [call.kwargs["timeout"] for call in receive.call_args_list] == [None, 9.0, 1.0]
    assert "different batch" in capsys.readouterr().err


def test_collect_batch_partial_timeout_returns_received_problems_and_warns(monkeypatch, capsys):
    first = make_problem_payload(batch={"id": "batch", "size": 2})
    factory = ServerFactory()
    monkeypatch.setattr(companion_listener, "_CompanionServer", factory)
    monkeypatch.setattr(companion_listener, "_receive", Mock(side_effect=[first, None]))
    monkeypatch.setattr(companion_listener.time, "monotonic", Mock(side_effect=[0.0, 1.0]))

    assert companion_listener.collect_batch() == [first]
    assert "received only 1 of 2" in capsys.readouterr().err


def test_collect_batch_deadline_already_expired_returns_received_problems_and_warns(monkeypatch, capsys):
    first = make_problem_payload(batch={"id": "batch", "size": 2})
    factory = ServerFactory()
    monkeypatch.setattr(companion_listener, "_CompanionServer", factory)
    monkeypatch.setattr(companion_listener, "_receive", Mock(return_value=first))
    monkeypatch.setattr(companion_listener.time, "monotonic", Mock(side_effect=[0.0, 11.0]))

    assert companion_listener.collect_batch() == [first]
    assert "received only 1 of 2" in capsys.readouterr().err


def test_collect_batch_server_construction_os_error_raises_cpt_error(monkeypatch):
    monkeypatch.setattr(companion_listener, "_CompanionServer", Mock(side_effect=OSError("busy")))

    with pytest.raises(CptError, match="Could not start"):
        companion_listener.collect_batch()


def test_collect_batch_closes_server_even_when_receive_raises(monkeypatch, sample_problem):
    factory = ServerFactory()
    monkeypatch.setattr(companion_listener, "_CompanionServer", factory)
    monkeypatch.setattr(companion_listener, "_receive", Mock(side_effect=RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        companion_listener.collect_batch()

    factory.server.server_close.assert_called_once_with()
