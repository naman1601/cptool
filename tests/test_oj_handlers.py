import pytest

import oj_handlers
from core import CptError
from tests.helpers import make_problem_payload


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Hello World", "Hello_World"),
        ("  Hello   World  ", "Hello_World"),
        ('a/b:c* d?e"f<g>h|i', "abc_defghi"),
        ("a\\b", "ab"),
        ("", "problem"),
        ("   ", "problem"),
        (".", "problem"),
        ("..", "problem"),
        ("///", "problem"),
        ("Bjorn", "Bjorn"),
    ],
)
def test_sanitize_path_segment_replaces_unsafe_segments(raw, expected):
    assert oj_handlers.sanitize_path_segment(raw) == expected


@pytest.mark.parametrize(
    ("group", "expected_type"),
    [
        ("Codeforces Round 999", oj_handlers.Codeforces),
        ("AtCoder Beginner Contest 400", oj_handlers.AtCoder),
        ("CodeChef Starters 999", oj_handlers.CodeChef),
        ("CSES Problem Set", oj_handlers.CSES),
        ("USACO 2025 US Open Contest Platinum", oj_handlers.USACO),
        ("Kattis", type(None)),
    ],
)
def test_detect_group_prefix_returns_matching_platform(group, expected_type):
    platform = oj_handlers.detect(make_problem_payload(group=group))

    assert isinstance(platform, expected_type)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("A. Sum", "a"),
        ("B1. Easy Version", "b1"),
        ("C2. Hard Version", "c2"),
        ("D12. Many Digits", "d12"),
        ("Ex. Extra", "ex"),
        ("Ex2. Extra Hard", "ex2"),
        ("Just A Title", "Just_A_Title"),
    ],
)
def test_codeforces_get_problem_name_parses_leading_problem_code(name, expected):
    platform = oj_handlers.Codeforces()

    assert platform.get_problem_name(make_problem_payload(name=name)) == expected


@pytest.mark.parametrize(
    ("url", "name", "expected"),
    [
        ("https://codeforces.com/contest/999/problem/A", "A. Sum", "codeforces/999/a"),
        ("https://codeforces.com/problemset/problem/1234/C", "C. Title", "codeforces/1234/c"),
        ("https://codeforces.com/contest/999", "A. Sum", "codeforces/999/a"),
    ],
)
def test_codeforces_get_path_extracts_contest_id(contests_dir, url, name, expected):
    platform = oj_handlers.Codeforces()

    path = platform.get_path(make_problem_payload(url=url, name=name), contests_dir)

    assert path == contests_dir / expected


def test_codeforces_get_path_unsupported_url_raises_cpt_error(contests_dir):
    platform = oj_handlers.Codeforces()

    with pytest.raises(CptError, match="Could not extract contest ID"):
        platform.get_path(make_problem_payload(url="https://example.com/problem/A"), contests_dir)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("C1. Split", "c1"),
        ("Ex. Extra Problem", "ex"),
        ("Ex2. Hard Version", "ex2"),
    ],
)
def test_atcoder_get_problem_name_uses_leading_problem_code(name, expected):
    platform = oj_handlers.AtCoder()

    assert platform.get_problem_name(make_problem_payload(name=name)) == expected


def test_atcoder_get_path_extracts_contest_id(contests_dir):
    platform = oj_handlers.AtCoder()
    problem = make_problem_payload(
        group="AtCoder Beginner Contest 400",
        url="https://atcoder.jp/contests/abc400/tasks/abc400_a",
    )

    path = platform.get_path(problem, contests_dir)

    assert path == contests_dir / "atcoder/abc400/a"


def test_atcoder_get_path_unsupported_url_raises_cpt_error(contests_dir):
    platform = oj_handlers.AtCoder()

    with pytest.raises(CptError, match="Could not extract contest ID"):
        platform.get_path(make_problem_payload(url="https://example.com/tasks/a"), contests_dir)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://codechef.com/START99/problems/FOOBAR", "foobar"),
        ("https://codechef.com/START99/problems/FOOBAR/", "foobar"),
    ],
)
def test_codechef_get_problem_name_uses_last_url_segment(url, expected):
    platform = oj_handlers.CodeChef()

    assert platform.get_problem_name(make_problem_payload(url=url)) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://codechef.com/START99/problems/FOOBAR", "codechef/start99/foobar"),
        ("https://codechef.com/problems/FOOBAR", "codechef/practice/foobar"),
        ("https://www.codechef.com/problems/FOOBAR", "codechef/practice/foobar"),
    ],
)
def test_codechef_get_path_resolves_contest_and_practice_paths(contests_dir, url, expected):
    platform = oj_handlers.CodeChef()

    path = platform.get_path(make_problem_payload(url=url), contests_dir)

    assert path == contests_dir / expected


def test_cses_get_problem_name_uses_last_two_path_segments():
    platform = oj_handlers.CSES()

    name = platform.get_problem_name(make_problem_payload(url="https://cses.fi/problemset/task/1234"))

    assert name == "task/1234"


def test_cses_get_path_uses_problem_set_layout(contests_dir):
    platform = oj_handlers.CSES()

    path = platform.get_path(make_problem_payload(url="https://cses.fi/problemset/task/1234/"), contests_dir)

    assert path == contests_dir / "cses/task/1234"


def test_cses_get_problem_name_short_url_raises_cpt_error():
    platform = oj_handlers.CSES()

    with pytest.raises(CptError, match="CSES problem name"):
        platform.get_problem_name(make_problem_payload(url="https://cses.fi/problemset"))


def test_cses_get_problem_name_sanitizes_trailing_segments_individually():
    platform = oj_handlers.CSES()

    name = platform.get_problem_name(make_problem_payload(url="https://cses.fi/problemset/task bad/a:b"))

    assert name == "task_bad/ab"


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"languages": {"java": {"taskClass": "MilkMeasurement"}}}, "MilkMeasurement"),
        ({"languages": {}}, "A._Sum"),
        ({"languages": []}, "A._Sum"),
        ({"languages": {"java": []}}, "A._Sum"),
        ({"languages": {"java": {"taskClass": ""}}}, "A._Sum"),
        ({"languages": {"java": {"taskClass": "Milk/Measure:ment"}}}, "MilkMeasurement"),
    ],
)
def test_usaco_get_problem_name_prefers_safe_java_task_class(payload, expected):
    platform = oj_handlers.USACO()

    assert platform.get_problem_name(make_problem_payload(**payload)) == expected


@pytest.mark.parametrize(
    ("group", "expected"),
    [
        ("USACO 2025 US Open Contest, Platinum", "usaco/2025USOpenContestPlatinum/a"),
        ("USACO - USACO 2025 US Open Contest Platinum", "usaco/2025USOpenContestPlatinum/a"),
        ("USACO - 2023 February, Gold", "usaco/2023FebruaryGold/a"),
    ],
)
def test_usaco_get_path_normalizes_contest_name(contests_dir, group, expected):
    platform = oj_handlers.USACO()

    path = platform.get_path(make_problem_payload(group=group, languages={"java": {"taskClass": "a"}}), contests_dir)

    assert path == contests_dir / expected


@pytest.mark.parametrize("group", ["USACO", "USACO - USACO"])
def test_usaco_get_path_missing_contest_raises_cpt_error(contests_dir, group):
    platform = oj_handlers.USACO()

    with pytest.raises(CptError, match="Could not extract a USACO contest"):
        platform.get_path(make_problem_payload(group=group), contests_dir)
