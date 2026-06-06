import json
import os
import shutil
from pathlib import Path

from core import (CPTOOL_DIR, CONFIG_PATH, TEMPLATES_DIR, CptError,
                  LanguageConfig, validate_config, validate_language_entry)
from problem_maker import seed_templates

EDITOR_PRIORITY = ['code', 'subl', 'vim', 'nvim', 'nano', 'gedit']

# Built-in language defaults, defined as LanguageConfig instances so the schema
# lives in exactly one place (core.LanguageConfig). run_init serializes these
# via to_dict() when writing a fresh config.json.
DEFAULT_LANGUAGES = {
    "cpp": LanguageConfig(
        name="cpp",
        extension=".cpp",
        source_file="code.cpp",
        template=str(TEMPLATES_DIR / 'template.cpp'),
        compile="g++ -std=c++17 -Wall -Wextra -Wshadow -D_GLIBCXX_DEBUG -ggdb3 -fsanitize=address -fsanitize=undefined {source} -o {executable}",
        run="{executable}",
        executable="code",
        comment="//",
    ),
    "python": LanguageConfig(
        name="python",
        extension=".py",
        source_file="code.py",
        template=str(TEMPLATES_DIR / 'template.py'),
        compile=None,
        run="python3 {source}",
        executable=None,
        comment="#",
    ),
}


def available_editors() -> list[str]:
    return [e for e in EDITOR_PRIORITY if shutil.which(e)]


def detect_editor() -> str:
    editors = available_editors()
    return editors[0] if editors else ''


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise CptError("Config not found. Run './cpt.py init' first.")
    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise CptError(f"config.json is not valid JSON: {e}")
    validate_config(config)
    return config


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def print_config(key: str = None) -> None:
    config = load_config()

    if key is None:
        print(json.dumps(config, indent=2))
        return

    current = config
    for part in key.split('.'):
        if not isinstance(current, dict) or part not in current:
            raise CptError(f"Key '{key}' not found.")
        current = current[part]
    print(json.dumps(current, indent=2))


def set_config(key: str, value: str) -> None:
    config = load_config()

    parts   = key.split('.')
    current = config
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise CptError(f"Key '{key}' not found in config.")
        current = current[part]

    target_key = parts[-1]
    if not isinstance(current, dict) or target_key not in current:
        raise CptError(f"Key '{key}' not found in config. (To add a language, use 'config add-language'.)")

    existing = current[target_key]
    if value.lower() == 'null':
        current[target_key] = None
    # bool must be checked before int: in Python bool is a subclass of int, so
    # isinstance(True, int) is True and the int branch would mishandle booleans.
    elif isinstance(existing, bool):
        current[target_key] = value.lower() in ('true', '1', 'yes')
    elif isinstance(existing, int):
        try:
            current[target_key] = int(value)
        except ValueError:
            raise CptError(f"'{value}' is not a valid integer for key '{key}'.")
    else:
        # str values, and previously-null fields (existing is None) that we are
        # now giving a real value.
        current[target_key] = value

    # Refuse a change that would make the file fail to load (e.g. clearing a
    # required string field with `null`), so the tool can't brick itself.
    validate_config(config)
    save_config(config)
    print(f'Set {key} = {current[target_key]}')


def add_language() -> None:
    config = load_config()
    print('Add a new language\n')

    name        = input('Language name (e.g. java, rust): ').strip()
    if not name:
        print('Language name cannot be empty.')
        return
    if name in config['languages']:
        print(f"Language '{name}' already exists. Overwrite it? [y/n]: ", end='')
        if input().strip() != 'y':
            return
    extension   = input('File extension (e.g. .java, .rs): ').strip()
    if not extension.startswith('.') or os.sep in extension:
        print("Extension must start with '.' and contain no path separators.")
        return
    source_file     = input(f'Source filename [code{extension}]: ').strip() or f'code{extension}'
    compile_command = input('Compile command (use {source}, {executable}; blank if none): ').strip() or None
    executable      = input('Executable name (blank if none): ').strip() or None
    run_command     = input('Run command (use {source}, {executable}): ').strip()
    if not run_command:
        print('Run command cannot be empty.')
        return
    default_comment = '#' if extension == '.py' else '//'
    comment         = input(f'Comment token [{default_comment}]: ').strip() or default_comment

    template_path   = TEMPLATES_DIR / f'template{extension}'
    template_source  = input('Template file to copy in (blank for empty file): ').strip()
    language_config = LanguageConfig(
        name=name,
        extension=extension,
        source_file=source_file,
        template=str(template_path),
        compile=compile_command,
        run=run_command,
        executable=executable,
        comment=comment,
    ).to_dict()
    validate_language_entry(name, language_config, require_complete=True)

    if template_source:
        source = Path(template_source).expanduser().resolve()
        if not source.is_file():
            print(f"File not found: {source}")
            return
        shutil.copy(source, template_path)
    else:
        template_path.touch()

    config['languages'][name] = language_config
    save_config(config)
    print(f"Language '{name}' added. Edit template at {template_path}")


def run_init() -> None:
    if CONFIG_PATH.exists():
        print(f'A config already exists at {CONFIG_PATH}.')
        print("Re-running init rebuilds it from scratch: languages added via "
              "'config add-language' and any manual edits will be lost.")
        if input('Overwrite it? [y/n]: ').strip() != 'y':
            print('Init cancelled; existing config left unchanged.')
            return

    editors        = available_editors()
    default_editor = editors[0] if editors else ''

    print('Welcome to cptool!\n')
    if editors:
        print(f'Detected editors: {", ".join(editors)}')

    editor        = input(f'Editor to use [{default_editor}]: ').strip() or default_editor
    language      = input('Default language (cpp/python) [cpp]: ').strip() or 'cpp'
    default_cp    = str(CPTOOL_DIR / 'contests')
    contests_path = input(f'Contests directory [{default_cp}]: ').strip() or default_cp
    contests_path = str(Path(contests_path).expanduser().resolve())

    config = {
        "contests_path": contests_path,
        "language": language,
        "editor": editor,
        "languages": {name: default.to_dict() for name, default in DEFAULT_LANGUAGES.items()}
    }

    if language not in config['languages']:
        raise CptError(f"Unknown language '{language}'. Choose one of: {', '.join(config['languages'])}.")
    # Guard against writing a config that wouldn't load (mirrors set_config).
    validate_config(config)

    seed_templates()
    save_config(config)
    print(f'\nConfig saved to {CONFIG_PATH}')
    print(f'Templates ready at {TEMPLATES_DIR}')
    print("You're ready to go!")
