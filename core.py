"""Shared foundation for cptool: filesystem locations and the LanguageConfig
domain type.

This module depends on nothing else in the project, so every other module can
import from it freely without risking an import cycle. It is the bottom layer.
"""
import os
from dataclasses import dataclass
from pathlib import Path

CPTOOL_DIR    = Path(__file__).parent
CONFIG_PATH   = CPTOOL_DIR / 'config.json'
TEMPLATES_DIR = CPTOOL_DIR / 'templates'


class CptError(Exception):
    """A known, user-actionable failure.

    Anything raised as CptError carries a message meant for the end user and is
    caught once in cpt.main(). Any *other* exception is treated as a bug and is
    allowed to surface as a traceback rather than being silently swallowed.
    """


@dataclass
class LanguageConfig:
    """Canonical schema for one entry in config['languages'].

    This dataclass is the single source of truth for the per-language shape:
    `for_active` reads it out of a config dict, `to_dict` serializes it back,
    and config.py derives both DEFAULT_LANGUAGES and the `add-language` output
    from it. `name` is the dict key in config['languages'], not part of the
    stored value, so `to_dict` omits it.

    `for_active(config)` is also the one place that resolves the active language
    (config['language']) against the table (config['languages']) — every other
    module asks for this object instead of repeating the easily-confused
    two-key lookup.
    """
    name: str
    extension: str
    source_file: str
    template: str | None
    compile: str | None
    run: str
    executable: str | None
    comment: str

    @classmethod
    def for_active(cls, config: dict) -> 'LanguageConfig':
        active  = config.get('language')
        configs = config.get('languages', {})
        if active not in configs:
            raise CptError(
                f"Active language '{active}' is not configured. "
                f"Add it with './cpt.py config add-language'."
            )
        data = configs[active]
        # Older config files predate the 'comment' field; infer a sensible
        # default from the extension so existing setups keep working.
        default_comment = '#' if data.get('extension') == '.py' else '//'
        return cls(
            name=active,
            extension=data.get('extension', ''),
            source_file=data['source_file'],
            template=data.get('template'),
            compile=data.get('compile'),
            run=data['run'],
            executable=data.get('executable'),
            comment=data.get('comment', default_comment),
        )

    def to_dict(self) -> dict:
        """Serialize to a config['languages'] entry (the `name` key is omitted)."""
        return {
            'extension':   self.extension,
            'source_file': self.source_file,
            'template':    self.template,
            'compile':     self.compile,
            'run':         self.run,
            'executable':  self.executable,
            'comment':     self.comment,
        }


# Top-level config.json keys that must be present for the tool to operate.
REQUIRED_CONFIG_KEYS = ('contests_path', 'language', 'languages')
# Per-language fields the reader (LanguageConfig.for_active) accesses directly.
REQUIRED_LANGUAGE_FIELDS = ('source_file', 'run')
# Per-language fields that, when present and non-null, must be strings.
STRING_LANGUAGE_FIELDS = ('extension', 'source_file', 'template', 'compile',
                          'run', 'executable', 'comment')


def validate_language_entry(name: str, data: dict, *, require_complete: bool = False) -> None:
    """Validate one config['languages'][name] entry.

    `require_complete=True` enforces the same invariants as an active language.
    The default mode only checks fields that are present, which is useful for
    partially-filled inactive entries that should remain loadable.
    """
    if not isinstance(data, dict):
        raise CptError(f"config.json: language '{name}' must be an object.")

    for field in STRING_LANGUAGE_FIELDS:
        value = data.get(field)
        if value is not None and not isinstance(value, str):
            raise CptError(f"config.json: language '{name}' field '{field}' must be a string.")

    if require_complete:
        for field in REQUIRED_LANGUAGE_FIELDS:
            if not data.get(field):
                raise CptError(f"config.json: language '{name}' is missing required field '{field}'.")

    # A compile step writes to {executable}, so the two must be configured together.
    if data.get('compile') and not data.get('executable'):
        raise CptError(f"config.json: language '{name}' has a 'compile' command but no 'executable'.")

    # source_file/executable are created and deleted inside the problem directory,
    # so they must be bare filenames — never absolute or containing separators.
    for field in ('source_file', 'executable'):
        value = data.get(field)
        if value and (os.path.isabs(value) or os.sep in value
                      or (os.altsep and os.altsep in value)):
            raise CptError(
                f"config.json: language '{name}' field '{field}' must be a bare filename, not a path: {value!r}"
            )

    if require_complete and data.get('compile') and data.get('executable') == data.get('source_file'):
        raise CptError(f"config.json: language '{name}' has 'executable' equal to 'source_file'.")


def validate_config(config: dict) -> None:
    """Check a freshly loaded config against the schema.

    Raises CptError with a config.json-prefixed message so a hand-edited or
    partial file fails clearly at load time instead of as a stray KeyError
    deep in a command.
    """
    if not isinstance(config, dict):
        raise CptError('config.json: top level must be a JSON object.')

    for key in REQUIRED_CONFIG_KEYS:
        if key not in config:
            raise CptError(f"config.json: missing required key '{key}'.")

    if not isinstance(config['contests_path'], str) or not config['contests_path'].strip():
        raise CptError("config.json: 'contests_path' must be a non-empty string.")
    if not isinstance(config['language'], str):
        raise CptError("config.json: 'language' must be a string.")
    if 'editor' in config and not isinstance(config['editor'], str):
        raise CptError("config.json: 'editor' must be a string.")

    languages = config['languages']
    if not isinstance(languages, dict) or not languages:
        raise CptError("config.json: 'languages' must be a non-empty object.")
    for name, data in languages.items():
        if not isinstance(data, dict):
            raise CptError(f"config.json: language '{name}' must be an object.")

    # Only the *active* language has to be complete — an unused half-built entry
    # shouldn't block commands that don't touch it.
    active = config['language']
    if active not in languages:
        raise CptError(f"config.json: active language '{active}' has no entry under 'languages'.")
    validate_language_entry(active, languages[active], require_complete=True)
