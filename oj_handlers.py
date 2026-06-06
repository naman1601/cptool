import re
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from pathlib import Path

from core import CptError


def sanitize_path_segment(name: str) -> str:
    """Turn free text into a safe single path segment.

    Strips path separators and reserved characters, collapses whitespace, and
    refuses '.'/'..'/empty so a crafted name can't traverse out of its directory.
    """
    cleaned = re.sub(r'[\\/:*?"<>|]', '', name).strip()
    cleaned = re.sub(r'\s+', '_', cleaned)
    if cleaned in ('', '.', '..'):
        return 'problem'
    return cleaned


def _contest_id_from_url(url: str, prefix: str) -> str | None:
    if prefix not in url:
        return None
    start = url.index(prefix) + len(prefix)
    end   = url.find('/', start)
    return url[start:end].lower() if end != -1 else url[start:].lower()


def _require_contest_id(contest_id: str | None, url: str) -> str:
    # Reject empty too: a prefix at the very end of the URL yields '' (not None).
    if not contest_id:
        raise CptError(f"Could not extract contest ID from URL: {url}")
    return contest_id


_PROBLEM_CODE_RE = re.compile(r'^(Ex\d*|[A-Za-z]\d*)\b')


# Codeforces and AtCoder name problems by letter: "A", "B", "C1", "C2", "Ex".
# The digit suffix handles split problems like C1/C2. "Ex2" is also valid for
# the extra problems that number their variants.
def _abc_problem_name(json_data: dict) -> str:
    name = json_data['name'].strip()
    match = _PROBLEM_CODE_RE.match(name)
    if match:
        return match.group(1).lower()
    # The convention is a leading problem code ("A. Foo", "C1. Bar"). If the
    # name doesn't follow it, fall back to a sanitized title instead of emitting
    # a meaningless single character.
    return sanitize_path_segment(name)


def _cses_problem_name(json_data: dict) -> str:
    path = urlparse(json_data['url']).path.strip('/')
    segments = [segment for segment in path.split('/') if segment]
    if len(segments) < 2:
        raise CptError(f"Could not extract a CSES problem name from URL: {json_data['url']}")
    # Keep the last two path segments so /problemset/task/1234 becomes task/1234.
    return '/'.join(sanitize_path_segment(segment) for segment in segments[-2:])


class Platform(ABC):
    group_prefix: str

    @abstractmethod
    def get_problem_name(self, json_data: dict) -> str:
        ...

    @abstractmethod
    def get_path(self, json_data: dict, contests_path: Path) -> Path:
        ...


class Codeforces(Platform):
    group_prefix = 'Codeforces'

    def get_problem_name(self, json_data: dict) -> str:
        return _abc_problem_name(json_data)

    # Problemset problems have a different URL format than contest problems:
    # /contest/<id>/problem/<letter> vs /problemset/problem/<id>/<letter>
    def get_path(self, json_data: dict, contests_path: Path) -> Path:
        contest_id = _require_contest_id(
            _contest_id_from_url(json_data['url'], 'codeforces.com/contest/')
            or _contest_id_from_url(json_data['url'], 'codeforces.com/problemset/problem/'),
            json_data['url'],
        )
        return contests_path / 'codeforces' / sanitize_path_segment(contest_id) / self.get_problem_name(json_data)


class AtCoder(Platform):
    group_prefix = 'AtCoder'

    def get_problem_name(self, json_data: dict) -> str:
        return _abc_problem_name(json_data)

    def get_path(self, json_data: dict, contests_path: Path) -> Path:
        contest_id = _require_contest_id(
            _contest_id_from_url(json_data['url'], 'atcoder.jp/contests/'),
            json_data['url'],
        )
        return contests_path / 'atcoder' / sanitize_path_segment(contest_id) / self.get_problem_name(json_data)


class CodeChef(Platform):
    group_prefix = 'CodeChef'

    # CodeChef problem names in CC data are full titles, not short IDs.
    # The URL's last segment is the canonical short problem code.
    def get_problem_name(self, json_data: dict) -> str:
        last = json_data['url'].rstrip('/').rsplit('/', 1)[-1]
        return sanitize_path_segment(last.lower())

    def get_path(self, json_data: dict, contests_path: Path) -> Path:
        contest_id = _require_contest_id(
            _contest_id_from_url(json_data['url'], 'codechef.com/'),
            json_data['url'],
        )
        # Practice problems are codechef.com/problems/<code> — no contest level.
        if contest_id == 'problems':
            contest_id = 'practice'
        return contests_path / 'codechef' / sanitize_path_segment(contest_id) / self.get_problem_name(json_data)


class CSES(Platform):
    group_prefix = 'CSES'

    # CSES URLs look like cses.fi/problemset/task/1234. Keeping the two trailing
    # path segments (e.g. "task/1234") mirrors the CSES site structure.
    def get_problem_name(self, json_data: dict) -> str:
        return _cses_problem_name(json_data)

    # CSES is a problem set, not a contest platform, so there is no contest level.
    def get_path(self, json_data: dict, contests_path: Path) -> Path:
        return contests_path / 'cses' / self.get_problem_name(json_data)


class USACO(Platform):
    group_prefix = 'USACO'

    # USACO problem names in CC data are full English titles. The Java task
    # class name is a consistent short identifier (e.g. "MilkMeasurement");
    # fall back to a sanitized title if no Java data is present.
    def get_problem_name(self, json_data: dict) -> str:
        # languages / java / taskClass are untrusted and optional; tolerate any
        # shape and fall back to the (validated, non-empty) problem name.
        languages  = json_data.get('languages')
        java       = languages.get('java') if isinstance(languages, dict) else None
        task_class = java.get('taskClass') if isinstance(java, dict) else None
        name       = task_class if isinstance(task_class, str) and task_class else json_data['name']
        return sanitize_path_segment(name)

    # CC sends the contest as "USACO <contest>" or "USACO - USACO <contest>".
    # Strip the prefix(es) and remove spaces/commas to get e.g. "2023FebruaryGold".
    def get_path(self, json_data: dict, contests_path: Path) -> Path:
        contest_id = (json_data['group']
                      .removeprefix(self.group_prefix)
                      .lstrip(' -')
                      .removeprefix(self.group_prefix)
                      .strip()
                      .replace(' ', '')
                      .replace(',', ''))
        if not contest_id:
            raise CptError(f"Could not extract a USACO contest from group: {json_data['group']!r}")
        return contests_path / 'usaco' / sanitize_path_segment(contest_id) / self.get_problem_name(json_data)


# Explicit registry: no import-time decorator side effects, and the set of
# supported platforms is visible in one place. Order matters only if prefixes
# overlap (they don't today).
PLATFORMS: list[Platform] = [
    Codeforces(),
    AtCoder(),
    CodeChef(),
    CSES(),
    USACO(),
]


def detect(json_data: dict) -> Platform | None:
    for platform in PLATFORMS:
        if json_data['group'].startswith(platform.group_prefix):
            return platform
    return None
