# Testing Guide

This document describes the pytest suite for `cptool`: how tests are organized,
what behavior they cover, and the conventions to follow when adding or extending
tests.

It is intentionally written for both humans and coding agents. The test cases
spell out expected behavior in enough detail that an agent can implement or
update the suite without guessing about scope, fixtures, side effects, or
acceptable shortcuts.

## Running Tests

Run the full suite from the repository root:

```bash
python3 -m pytest -q
```

Use verbose output while debugging:

```bash
python3 -m pytest -vv
```

## Directory Layout

Tests live under `tests/` and are split by production module:

```text
tests/
  conftest.py
  helpers.py
  test_core.py
  test_config.py
  test_oj_handlers.py
  test_problem_maker.py
  test_cpt_runtime.py
  test_companion_listener.py
  test_cli.py
```

Responsibilities:

- `conftest.py`: shared pytest fixtures.
- `helpers.py`: pure helper functions used by multiple test files.
- `test_core.py`: `core.py` dataclasses and config validation.
- `test_config.py`: config file I/O and interactive config commands.
- `test_oj_handlers.py`: platform detection, path sanitization, and problem
  paths.
- `test_problem_maker.py`: template seeding, problem creation, and testcase
  writes.
- `test_cpt_runtime.py`: command building, compilation, testcase execution,
  output normalization, result reporting, and `cpt.test`.
- `test_companion_listener.py`: payload validation and batch receive behavior.
- `test_cli.py`: lightweight `cpt.main` routing and error handling.

## Test Style

Use pytest idioms:

- Plain `assert`, not `unittest.TestCase`.
- `pytest.raises` for exceptions.
- `@pytest.mark.parametrize` for repeated input/output cases.
- `tmp_path` for filesystem tests.
- `monkeypatch` for module constants, functions, current directory, and
  `builtins.input`.
- `capsys` for stdout and stderr assertions.
- `unittest.mock.Mock` is fine for call assertions.

Use arrange, act, assert structure in every test. The structure should be clear
from naming and spacing. Prefer clearer variable names, smaller fixtures, or
split tests over comments that merely explain test mechanics.

Test names should describe observable behavior:

```text
test_<function>_<condition>_<expected_behavior>
```

Examples:

- `test_sanitize_path_segment_replaces_whitespace_with_single_underscore`
- `test_validate_config_rejects_missing_active_language_entry`
- `test_make_problem_reuses_existing_code_file_and_rewrites_testcases`
- `test_collect_batch_ignores_problem_from_different_batch`

Fixture names should describe the resource they return:

- `sample_problem`
- `sample_config`
- `contests_dir`
- `template_file`
- `python_language`
- `cpp_language`

Mock names should describe the dependency they replace:

- `opened_editor`
- `saved_config`
- `received_problem`
- `run_checked`

## Shared Helpers

Put pure helpers in `tests/helpers.py`.

### `make_problem_payload(**overrides)`

Return a complete Competitive Companion-like payload:

```python
{
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
```

Apply overrides shallowly.

### `make_config(contests_path, language="python", **overrides)`

Return a valid config dict:

```python
{
    "contests_path": str(contests_path),
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
```

Apply overrides shallowly. For nested updates, copy and mutate the nested dict in
the test so the intended config shape remains visible.

### `write_json(path, data)`

Write JSON to `path` with indentation.

### `strip_ansi(text)`

Strip ANSI color escape sequences from captured output. Use this for
`cpt.report_result` and `cpt.test` assertions so color output does not make tests
brittle.

## Shared Fixtures

Put pytest fixtures in `tests/conftest.py`.

Recommended fixtures:

- `contests_dir(tmp_path)`: returns `tmp_path / "contests"` and creates it.
- `templates_dir(tmp_path)`: returns `tmp_path / "templates"` and creates it.
- `config_path(tmp_path)`: returns `tmp_path / "config.json"`.
- `sample_problem()`: returns `make_problem_payload()`.
- `sample_config(contests_dir)`: returns `make_config(contests_dir)`.
- `python_language(sample_config)`: returns active python language config data.
- `cpp_language(sample_config)`: returns cpp language config data.

Do not hide important test-specific setup inside fixtures. Use fixtures for
common stable resources only.

## Global Rules

- No network calls.
- Do not bind the real Competitive Companion port `1327`.
- Do not launch a real editor.
- Do not depend on `g++`, browser extensions, user config, or repo-local
  `config.json`.
- Write only inside `tmp_path`.
- Patch module-level paths before calling functions that use them.
- Assert `CptError` for user-actionable failures.
- Assert exact return values and important message substrings.
- Prefer testing public functions, but private helpers are acceptable when they
  contain important behavior that is intentionally factored into private
  functions.

## Coverage by Module

### `core.py`

`LanguageConfig.for_active` should cover:

- valid active python config returns the expected dataclass fields.
- valid active cpp config returns compile/run/executable fields.
- missing legacy `comment` defaults to `#` for `.py`.
- missing legacy `comment` defaults to `//` for non-python extensions.
- active language missing from `languages` raises `CptError` with
  `Active language`.

`validate_language_entry` should cover:

- complete interpreted language passes.
- complete compiled language passes.
- inactive partial language passes when `require_complete=False`.
- language entry is not an object.
- optional string fields reject non-string values: `extension`, `source_file`,
  `template`, `compile`, `run`, `executable`, `comment`.
- required `source_file` is missing or empty when `require_complete=True`.
- required `run` is missing or empty when `require_complete=True`.
- compile command is configured without executable.
- `source_file` is absolute.
- `source_file` contains a path separator.
- `executable` contains a path separator.
- executable equals source file for a compiled language.

For each failure, assert `pytest.raises(CptError)` and an identifying message
substring.

`validate_config` should cover:

- complete sample config passes.
- config without optional `editor` passes.
- inactive partial language entry passes if the active language is complete.
- unknown top-level keys are tolerated.
- top level is not an object.
- missing `contests_path`, `language`, or `languages`.
- `contests_path` is empty, whitespace-only, or non-string.
- `language` is non-string.
- `editor` is non-string.
- `languages` is empty or non-object.
- any language entry is non-object.
- active language has no matching language entry.
- active language violates `validate_language_entry`.

Assert messages contain `config.json:` for config schema errors.

### `config.py`

Patch `config.CONFIG_PATH` for config file tests.

`load_config` should cover:

- missing config file raises `CptError` with `Config not found`.
- invalid JSON raises `CptError` with `not valid JSON`.
- schema-invalid JSON raises `CptError` from validation.
- valid JSON returns the parsed dict.

`save_config` should cover:

- writes JSON that loads back to the same dict.
- output is indented enough to be human-readable.

`print_config` should cover:

- no key prints the full config as JSON.
- dotted key prints nested scalar as JSON.
- dotted key prints nested object as JSON.
- missing key raises `CptError`.
- attempting to traverse through a scalar raises `CptError`.

`set_config` should use a real temp file instead of mocking save/load where
possible. It should cover:

- setting string field updates and saves.
- setting a previously-null optional language field stores a string.
- setting an existing integer field coerces to int.
- setting an existing boolean field coerces truthy strings to `True` and other
  strings to `False`.
- missing intermediate key raises `CptError`.
- missing leaf key raises `CptError` mentioning `config add-language`.
- invalid integer string raises `CptError`.
- setting active language `run` to literal `null` raises `CptError` and does not
  save.
- setting `editor` to literal `null` raises `CptError` if validation requires
  `editor`, when present, to be a string.

`add_language` should patch `builtins.input` and `config.TEMPLATES_DIR`. It
should cover:

- adds interpreted ruby language with default source file and empty template.
- adds compiled rust language and copies a provided template file.
- overwrites existing language only when the user enters exact `y`.
- empty language name returns early.
- existing language overwrite declined returns early.
- extension without leading dot returns early.
- extension containing a path separator returns early.
- empty run command returns early.
- template source path does not exist returns early.
- compile command with blank executable raises `CptError`, does not write a
  template, and does not save config.

`run_init` should patch `config.CONFIG_PATH`, `config.TEMPLATES_DIR`,
`config.CPTOOL_DIR` where needed, `config.available_editors`,
`config.seed_templates`, and `builtins.input`. It should cover:

- fresh init with blank inputs writes valid default config and seeds templates.
- detected editor becomes the default editor when user input is blank.
- existing config overwrite declined leaves file unchanged.
- existing config overwrite accepted replaces file.
- unknown requested language raises `CptError` and does not save a config.

### `oj_handlers.py`

`sanitize_path_segment` should be parameterized:

| input | expected |
| --- | --- |
| `"Hello World"` | `"Hello_World"` |
| `"  Hello   World  "` | `"Hello_World"` |
| `"a/b:c* d?e\"f<g>h|i"` | `"abc_defghi"` |
| `"a\\b"` | `"ab"` |
| `""` | `"problem"` |
| `"   "` | `"problem"` |
| `"."` | `"problem"` |
| `".."` | `"problem"` |
| `"///"` | `"problem"` |
| `"Bjorn"` | `"Bjorn"` |

`detect` should cover:

- `Codeforces Round 999` -> `Codeforces`.
- `AtCoder Beginner Contest 400` -> `AtCoder`.
- `CodeChef Starters 999` -> `CodeChef`.
- `CSES Problem Set` -> `CSES`.
- `USACO 2025 US Open Contest Platinum` -> `USACO`.
- `Kattis` -> `None`.

Codeforces behavior should cover:

- `A. Sum` -> `a`.
- `B1. Easy Version` -> `b1`.
- `C2. Hard Version` -> `c2`.
- `D12. Many Digits` -> `d12`.
- `Ex. Extra` -> `ex`.
- `Ex2. Extra Hard` -> `ex2`.
- `Just A Title` -> `Just_A_Title`.
- contest URL -> `/contests/codeforces/999/a`.
- problemset URL -> `/contests/codeforces/1234/c`.
- contest URL without trailing problem segment still extracts contest id.
- URL without supported contest/problemset prefix raises `CptError`.

AtCoder behavior should cover:

- problem name parsing follows the same leading-code behavior as Codeforces.
- `https://atcoder.jp/contests/abc400/tasks/abc400_a` -> `abc400/a`.
- unsupported URL raises `CptError`.

CodeChef behavior should cover:

- `https://codechef.com/START99/problems/FOOBAR` -> `foobar`.
- trailing slash still resolves to `foobar`.
- contest path -> `codechef/start99/foobar`.
- practice path `https://codechef.com/problems/FOOBAR` ->
  `codechef/practice/foobar`.
- `https://www.codechef.com/problems/FOOBAR` currently raises `CptError`.
  Update this expectation if production code changes to support `www.`.

CSES behavior should cover:

- task URL returns problem name `task/1234`.
- full path is `/contests/cses/task/1234`.
- trailing slash is tolerated.
- short URL raises `CptError`.
- unsafe trailing path segments are sanitized segment by segment.

USACO behavior should cover:

- Java `taskClass` is preferred.
- missing `languages` falls back to sanitized `name`.
- non-dict `languages` falls back to sanitized `name`.
- non-dict `languages["java"]` falls back to sanitized `name`.
- empty `taskClass` falls back to sanitized `name`.
- unsafe `taskClass` characters are sanitized.
- `USACO 2025 US Open Contest, Platinum` ->
  `usaco/2025USOpenContestPlatinum/<problem>`.
- `USACO - USACO 2025 US Open Contest Platinum` ->
  `usaco/2025USOpenContestPlatinum/<problem>`.
- `USACO - 2023 February, Gold` ->
  `usaco/2023FebruaryGold/<problem>`.
- `USACO` raises `CptError`.
- `USACO - USACO` raises `CptError`.

### `problem_maker.py`

Patch module-level paths and editor-opening functions.

`seed_templates` should cover:

- copies every `default.*` file to matching `template.*` when missing.
- does not overwrite existing user template.
- ignores files that do not match `default.*`.

`_resolve_target_path` should cover:

- known platform returns platform path.
- unknown platform returns `unknown/<sanitized problem name>` and prints warning.
- fake platform returning a path outside contests dir raises `CptError`.

`_create_code_file` should cover:

- creates parent directories.
- writes URL, time limit, and memory limit metadata.
- appends existing template content.
- uses only metadata header when template is missing or `None`.
- uses `?` for missing limits.
- uses configured comment token.

`_write_testcases` should cover:

- writes input and answer files in order.
- removes stale `in*.txt` and `ans*.txt`.
- empty test list removes stale testcase files.
- `tests` is not a list.
- testcase is not a dict.
- testcase missing `input`.
- testcase missing `output`.
- testcase input is not a string.
- testcase output is not a string.
- malformed testcase does not remove existing stale files before raising.

`make_problem` should cover:

- new Codeforces problem creates directory, code file, metadata header,
  testcases, ready message, and editor call.
- existing code file is not overwritten, but testcases are refreshed.
- unknown OJ creates under `unknown/` and prints warning.
- active language not configured raises `CptError` and creates no problem dir.
- malformed tests may leave the newly created code file because current
  production order creates code before writing tests; assert no partial testcase
  set is written.

`gen` should run inside `tmp_path` with `monkeypatch.chdir(tmp_path)` and cover:

- missing source and existing template copies template.
- missing source and missing template creates empty source.
- existing source with answer `n` leaves file unchanged.
- existing source with answer `y` overwrites from template.
- any answer other than exact `y` leaves file unchanged.

### `cpt.py`

`build_command` should cover:

- simple source substitution.
- quoted executable path with spaces remains one token.
- quoted source path with spaces remains one token.
- compile command with multiple flags tokenizes as expected.
- empty command template raises `CptError`.
- whitespace-only command template raises `CptError`.
- invalid shell quoting raises `CptError`.
- unknown placeholder raises `CptError`.
- malformed format string raises `CptError`.

`run_checked` should patch `subprocess.run` and cover:

- returns successful `CompletedProcess`.
- `FileNotFoundError` becomes `CptError` with `Command not found`.
- generic `OSError` becomes `CptError` with `Could not run`.

`compile_solution` should use `tmp_path` and cover:

- removes stale executable before compile.
- returns `True` when compile succeeds and executable exists.
- returns `False` and prints `COMPILATION ERROR` for nonzero return code.
- returns `False` and prints `COMPILATION ERROR` when executable is missing.
- propagates `CptError` from command construction or execution.

`resolve_run_command` should cover:

- compiled language substitutes full executable path.
- interpreted language substitutes source and empty executable.

`run_testcase` should patch `cpt.run_checked` and cover:

- passes input file handle as stdin.
- captures stdout and stderr with `subprocess.PIPE`.
- runs in provided cwd.

`_normalize_lines` should be parameterized:

- strips surrounding whitespace from each line.
- drops trailing blank lines.
- keeps internal blank lines.
- empty string returns `[]`.
- whitespace-only string returns `[]`.

`report_result` should use `tmp_path` for input and answer files and cover:

- accepted output prints passed message.
- trailing whitespace and trailing blank lines are ignored.
- wrong answer prints input, expected output, and actual output.
- missing answer file prints skip message.
- runtime error with stdout prints stdout block.
- runtime error with stderr prints stderr block.
- runtime error with undecodable bytes does not crash.

`test` should use `monkeypatch.chdir(tmp_path)` and cover:

- compiled language stops when compile fails.
- compiled language runs contiguous testcases when compile succeeds.
- interpreted language skips compile.
- input scan stops at first missing index.
- no `in0.txt` prints no-testcases message.
- each contiguous testcase is reported, even if one result is a runtime error.

### `companion_listener.py`

`_validate` should cover:

- complete payload passes.
- missing each required field fails.
- `name`, `group`, or `url` is empty.
- `name`, `group`, or `url` is whitespace-only.
- `name`, `group`, or `url` is non-string.
- `batch` is not a dict.
- `batch.size` is missing.
- `batch.size` is zero.
- `batch.size` is negative.
- `batch.size` is bool.
- `batch.size` is string.

`_receive` should use a small fake server object with `timeout`, `received`,
`timed_out`, and `handle_request`. It should cover:

- returns received problem.
- timeout returns `None`.
- rejected request loops until later valid problem.

`collect_batch` should patch `_CompanionServer`, `_receive`, and
`time.monotonic`. It should cover:

- single-problem batch returns first problem and closes server.
- complete multi-problem batch returns all same-id problems.
- wrong batch id is ignored and warning is printed.
- partial timeout returns received problems and prints warning.
- deadline already expired returns received problems and prints warning.
- server construction `OSError` raises `CptError`.
- server closes even when `_receive` raises.

Optional HTTP handler tests may bind to port `0`, not `1327`. They should cover:

- valid JSON POST gets HTTP 200 and sets `server.received`.
- invalid JSON POST gets HTTP 400.
- schema-invalid JSON POST gets HTTP 400.

These HTTP tests are optional because `_validate`, `_receive`, and
`collect_batch` cover the important behavior without real sockets.

### CLI Routing in `cpt.py`

Keep `tests/test_cli.py` lightweight. Patch `cpt.docopt`, `cpt.load_config`, and
target functions.

`cpt.main` should cover:

- `init` routes to `run_init` without loading config.
- `config add-language` routes to `add_language`.
- `config <key>` routes to `print_config`.
- `config <key> <value>` routes to `set_config`.
- `e` or `--echo` routes to `collect_batch` and prints payloads without loading
  config.
- `t` or `--test` loads config and calls `test`.
- `g` or `--gen` loads config and calls `gen`.
- default command loads config, collects batch, and calls `make_problem` once per
  problem.
- `CptError` is printed and exits with code `1`.
- `OSError` is printed as `File system error: ...` and exits with code `1`.
- `KeyboardInterrupt` and `EOFError` print `Cancelled.` and exit with code
  `130`.

## Optional Smoke Tests

Create `tests/test_smoke.py` only if the unit suite is already stable.

Acceptable smoke tests:

- `python3 cpt.py --help` exits successfully and prints usage.
- direct `make_problem` plus `cpt.test` flow for a python solution inside
  `tmp_path`.

Do not add smoke tests that require:

- real Competitive Companion.
- real browser.
- real editor.
- `g++`.
- user config.
- network access.

## Completion Criteria

The test suite is complete when:

- `python3 -m pytest -q` passes from the repo root.
- No test reads or writes repo-local `config.json`.
- No test opens an editor or binds port `1327`.
- Tests are split by production module.
- Parameterized cases are used where they make failures clearer.
- Every test has clear arrange, act, assert flow.
- Test names describe behavior without needing comments.
- Behavior previously covered by legacy tests remains covered in the split pytest
  suite.
