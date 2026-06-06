import shlex
import shutil
import subprocess
from pathlib import Path

import oj_handlers
from core import LanguageConfig, TEMPLATES_DIR, CptError


def seed_templates() -> None:
    """Copy bundled default.* templates to template.* unless one already exists.

    Re-running never clobbers a user's edited template.
    """
    for default_template in TEMPLATES_DIR.glob('default.*'):
        user_template = TEMPLATES_DIR / f'template{default_template.suffix}'
        if not user_template.exists():
            shutil.copy(default_template, user_template)


def open_in_editor(editor: str, code_file: Path) -> None:
    if not editor or not shutil.which(editor):
        return
    try:
        subprocess.Popen([editor, str(code_file)])
    except OSError as e:
        print(f"Warning: could not launch editor '{editor}': {e}")


def _resolve_target_path(json_data: dict, contests_path: Path) -> Path:
    platform = oj_handlers.detect(json_data)
    if platform is None:
        print(f"Warning: unknown OJ '{json_data['group']}', filing under 'unknown'")
        target = contests_path / 'unknown' / oj_handlers.sanitize_path_segment(json_data['name'])
    else:
        target = platform.get_path(json_data, contests_path)

    # Defense in depth: the payload is untrusted (arbitrary JSON over a local
    # HTTP POST), so never let a crafted name/url escape the contests directory.
    if not target.resolve().is_relative_to(contests_path.resolve()):
        raise CptError(f"Refusing to create a problem outside the contests directory: {target}")
    return target


def _create_code_file(code_file: Path, language: LanguageConfig, json_data: dict) -> None:
    code_file.parent.mkdir(parents=True, exist_ok=True)
    comment_token = language.comment
    header = (
        f'{comment_token} url: {json_data.get("url", "")}\n'
        f'{comment_token} time limit: {json_data.get("timeLimit", "?")}s\n'
        f'{comment_token} memory limit: {json_data.get("memoryLimit", "?")}MB\n'
    )
    template_content = ''
    if language.template and Path(language.template).is_file():
        with open(language.template) as f:
            template_content = f.read()
    code_file.write_text(header + template_content)


def _write_testcases(target_path: Path, tests: list) -> None:
    if not isinstance(tests, list):
        raise CptError("Problem payload field 'tests' is not a list.")
    # Validate every testcase up front so a malformed entry can't leave a
    # half-written, inconsistent set on disk (all-or-nothing).
    for idx, testcase in enumerate(tests):
        if not isinstance(testcase, dict) or 'input' not in testcase or 'output' not in testcase:
            raise CptError(f"Testcase #{idx} is missing 'input' or 'output'.")
        if not isinstance(testcase['input'], str) or not isinstance(testcase['output'], str):
            raise CptError(f"Testcase #{idx} has a non-string 'input' or 'output'.")
    # Clear any testcases from a previous parse so the on-disk set always matches
    # the current payload — otherwise test() would run stale leftover cases.
    for stale in (*target_path.glob('in*.txt'), *target_path.glob('ans*.txt')):
        stale.unlink()
    for idx, testcase in enumerate(tests):
        (target_path / f'in{idx}.txt').write_text(testcase['input'])
        (target_path / f'ans{idx}.txt').write_text(testcase['output'])


def make_problem(json_data: dict, config: dict) -> None:
    language    = LanguageConfig.for_active(config)
    target_path = _resolve_target_path(json_data, Path(config['contests_path']))
    code_file   = target_path / language.source_file

    if code_file.is_file():
        print('Code file already exists! Re-parsing testcases.')
    else:
        _create_code_file(code_file, language, json_data)

    _write_testcases(target_path, json_data.get('tests', []))

    print(f'Problem ready:\ncd {shlex.quote(str(target_path))}')

    open_in_editor(config.get('editor', ''), code_file)


def gen(config: dict) -> None:
    language  = LanguageConfig.for_active(config)
    code_file = Path.cwd() / language.source_file

    if code_file.is_file():
        print(f'{language.source_file} already exists. Overwrite with template? [y/n]: ', end='')
        if input().strip() != 'y':
            return

    if language.template and Path(language.template).is_file():
        shutil.copy(language.template, code_file)
    else:
        code_file.touch()
    print(f'Created {code_file}')
