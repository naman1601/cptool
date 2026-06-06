import json
import re


def make_problem_payload(**overrides):
    payload = {
        "name": "A. Sum",
        "group": "Codeforces Round 999",
        "url": "https://codeforces.com/contest/999/problem/A",
        "interactive": False,
        "memoryLimit": 256,
        "timeLimit": 2,
        "tests": [
            {"input": "1 2\n", "output": "3\n"},
            {"input": "10 20\n", "output": "30\n"},
        ],
        "testType": "single",
        "input": {"type": "stdin"},
        "output": {"type": "stdout"},
        "languages": {},
        "batch": {"id": "batch-1", "size": 1},
    }
    payload.update(overrides)
    return payload


def make_config(contests_dir, language="python", **overrides):
    config = {
        "contests_path": str(contests_dir),
        "language": language,
        "editor": "",
        "languages": {
            "python": {
                "extension": ".py",
                "source_file": "code.py",
                "template": None,
                "compile": None,
                "run": "python3 {source}",
                "executable": None,
                "comment": "#",
            },
            "cpp": {
                "extension": ".cpp",
                "source_file": "code.cpp",
                "template": None,
                "compile": "g++ {source} -o {executable}",
                "run": "{executable}",
                "executable": "code",
                "comment": "//",
            },
        },
    }
    config.update(overrides)
    return config


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2))


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)
