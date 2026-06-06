import pytest

from tests.helpers import make_config, make_problem_payload


@pytest.fixture
def contests_dir(tmp_path):
    path = tmp_path / "contests"
    path.mkdir()
    return path


@pytest.fixture
def templates_dir(tmp_path):
    path = tmp_path / "templates"
    path.mkdir()
    return path


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "config.json"


@pytest.fixture
def sample_problem():
    return make_problem_payload()


@pytest.fixture
def sample_config(contests_dir):
    return make_config(contests_dir)


@pytest.fixture
def python_language(sample_config):
    return sample_config["languages"]["python"]


@pytest.fixture
def cpp_language(sample_config):
    return sample_config["languages"]["cpp"]
