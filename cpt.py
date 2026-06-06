#!/usr/bin/python3
"""cptool — download and test competitive programming problems
Usage:
  cpt.py
  cpt.py init
  cpt.py config
  cpt.py config <key> [<value>]
  cpt.py config add-language
  cpt.py t
  cpt.py --test
  cpt.py e
  cpt.py --echo
  cpt.py g
  cpt.py --gen

Options:
  -h --help    Show this screen
  t, --test    Test your code against downloaded/custom testcases
  e, --echo    Echo received Competitive Companion responses and exit
  g, --gen     Generate code file from template in current directory

Commands:
  init                   Interactive first-run configuration wizard
  config                 Show full config
  config <key>           Show a specific config value
  config <key> <value>   Set a config value
  config add-language    Add a new language interactively
"""

import shlex
import subprocess
import sys
from pathlib import Path

from docopt import docopt
from colorama import Fore, Style

from core import LanguageConfig, CptError
from config import load_config, run_init, print_config, set_config, add_language
from companion_listener import collect_batch
from problem_maker import make_problem, gen


def build_command(template: str, **subs: str) -> list[str]:
    """Split a command template into argv tokens, then substitute placeholders.

    Splitting before substituting means a value containing spaces (e.g. an
    executable path under '/home/me/my problems/') stays a single argv token
    instead of being re-split by the shell tokenizer.
    """
    try:
        tokens = shlex.split(template)
    except ValueError as e:
        raise CptError(f"Invalid command template {template!r} (check quoting): {e}")
    if not tokens:
        raise CptError("Command template is empty.")
    try:
        return [token.format(**subs) for token in tokens]
    except (KeyError, IndexError, ValueError) as e:
        raise CptError(
            f"Invalid placeholder in command template {template!r}: {e}. "
            f"Only {{source}} and {{executable}} are available."
        )


def run_checked(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run that turns a missing/uninvokable command into a CptError."""
    try:
        return subprocess.run(cmd, **kwargs)
    except FileNotFoundError:
        raise CptError(f"Command not found: '{cmd[0]}'. Is it installed and on your PATH?")
    except OSError as e:
        raise CptError(f"Could not run '{cmd[0]}': {e}")


def compile_solution(language: LanguageConfig, cwd: Path) -> bool:
    """Compile the solution. Returns True on success, prints an error otherwise."""
    executable_path = cwd / language.executable
    if executable_path.is_file():
        executable_path.unlink()

    cmd    = build_command(language.compile, source=language.source_file, executable=language.executable)
    result = run_checked(cmd, cwd=cwd)

    if result.returncode != 0 or not executable_path.is_file():
        print(Fore.RED + 'COMPILATION ERROR' + Style.RESET_ALL)
        return False
    return True


def resolve_run_command(language: LanguageConfig, cwd: Path) -> list[str]:
    executable = str(cwd / language.executable) if language.compile else ''
    return build_command(language.run, source=language.source_file, executable=executable)


def run_testcase(run_cmd: list[str], input_file: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Run one testcase and return the completed process."""
    with open(input_file) as fin:
        return run_checked(
            run_cmd, stdin=fin,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=cwd,
        )


def _normalize_lines(text: str) -> list[str]:
    """Split into stripped lines, dropping trailing blank lines."""
    lines = [line.strip() for line in text.splitlines()]
    while lines and lines[-1] == '':
        lines.pop()
    return lines


def report_result(idx: int, result: subprocess.CompletedProcess,
                  input_file: Path, answer_file: Path) -> None:
    if result.returncode != 0:
        print(Fore.RED + f'Runtime error on testcase #{idx}' + Style.RESET_ALL)
        stdout_output = result.stdout.decode(errors='replace').strip() if result.stdout else ''
        stderr_output = result.stderr.decode(errors='replace').strip() if result.stderr else ''
        if stdout_output:
            print(Fore.CYAN + 'Stdout:' + Style.RESET_ALL)
            print(stdout_output)
        if stderr_output:
            print(Fore.CYAN + 'Stderr:' + Style.RESET_ALL)
            print(stderr_output)
        return

    if not answer_file.is_file():
        print(Fore.YELLOW + f'No answer file for testcase #{idx}, skipping.' + Style.RESET_ALL)
        return

    program_output = result.stdout.decode(errors='replace')
    # Compare line-by-line with each line stripped, and ignore trailing blank
    # lines on both sides, so trailing whitespace / newlines / a stray blank
    # line at the end don't cause a spurious WA.
    output_lines = _normalize_lines(program_output)
    answer_lines = _normalize_lines(answer_file.read_text())

    if output_lines == answer_lines:
        print(Fore.GREEN + f'Passed testcase #{idx}' + Style.RESET_ALL)
    else:
        print(Fore.RED + f'WA on testcase #{idx}' + Style.RESET_ALL)
        print(Fore.CYAN + 'Input:\n'       + Style.RESET_ALL + input_file.read_text())
        print(Fore.CYAN + 'Expected:\n'    + Style.RESET_ALL + answer_file.read_text().strip())
        print(Fore.CYAN + 'Your output:\n' + Style.RESET_ALL + program_output.strip())


def test(config: dict) -> None:
    language = LanguageConfig.for_active(config)
    cwd      = Path.cwd()

    if language.compile and not compile_solution(language, cwd):
        return

    run_cmd = resolve_run_command(language, cwd)

    idx = 0
    while True:
        input_file = cwd / f'in{idx}.txt'
        if not input_file.is_file():
            break
        answer_file = cwd / f'ans{idx}.txt'
        result      = run_testcase(run_cmd, input_file, cwd)
        report_result(idx, result, input_file, answer_file)
        idx += 1

    if idx == 0:
        print(Fore.YELLOW + 'No testcases found (expected in0.txt in this directory).' + Style.RESET_ALL)


def main() -> None:
    args = docopt(__doc__)

    try:
        if args['init']:
            run_init()
            return

        if args['config']:
            if args['<key>'] == 'add-language':
                add_language()
            elif args['<value>']:
                set_config(args['<key>'], args['<value>'])
            else:
                print_config(args['<key>'])
            return

        if args['e'] or args['--echo']:
            # Echo only inspects the wire payload and needs no config — run it
            # before load_config() so it works before 'cpt.py init' is done.
            for problem in collect_batch():
                print(problem)
            return

        config = load_config()

        if args['t'] or args['--test']:
            test(config)
            return

        if args['g'] or args['--gen']:
            gen(config)
            return

        for problem in collect_batch():
            make_problem(problem, config)

    except CptError as e:
        # Known, user-actionable failures: show the message, no traceback.
        print(e)
        sys.exit(1)
    except OSError as e:
        # Filesystem/environment failures (permissions, bad path, disk) reaching
        # this far are user-actionable, not bugs — report them cleanly too.
        print(f'File system error: {e}')
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled.')
        sys.exit(130)


if __name__ == '__main__':
    main()
