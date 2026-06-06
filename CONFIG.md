# Configuration Reference

cptool stores its settings in `config.json`, located alongside the script
(`cptool/config.json`). The file is created by `./cpt.py init` and validated
every time it is loaded — an invalid file produces a clear error rather than a
crash.

You can change settings three ways:

- `./cpt.py config <key> <value>` — set a single value (dotted keys for nesting).
- `./cpt.py config add-language` — add a language interactively.
- Editing `config.json` by hand — it is plain JSON.

---

## Top-level fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `contests_path` | string | yes | Absolute path to the directory under which contest/problem folders are created. |
| `language` | string | yes | The **active** language: a key into the `languages` object. Determines which language `t`/`g`/parsing use. |
| `editor` | string | no | Command used to open new problem files (e.g. `code`, `nvim`). Empty disables auto-open. |
| `languages` | object | yes | Map of language name → [language definition](#language-definition). Must contain at least the active language. |

---

## Language definition

Each entry under `languages` describes one language. The map key (e.g. `"cpp"`)
is the language's name; it is not repeated inside the object.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `extension` | string | recommended | File extension including the dot (e.g. `.cpp`). Used to name the template file and to infer the default comment token. |
| `source_file` | string | **yes** | Name of the solution file created in each problem directory (e.g. `code.cpp`). |
| `template` | string \| null | no | Absolute path to a template file whose contents seed new solution files. `null` or a missing file → an empty body. |
| `compile` | string \| null | no | Compile command template. `null` marks an interpreted language (no compile step). See [placeholders](#command-placeholders). |
| `run` | string | **yes** | Command template used to run the solution. See [placeholders](#command-placeholders). |
| `executable` | string \| null | no | Name of the compiled binary (e.g. `code`). Required for compiled languages; `null` for interpreted ones. |
| `comment` | string | no | Line-comment token (e.g. `//`, `#`) used for the metadata header written at the top of new solution files. Defaults to `#` for `.py`, otherwise `//`. |

Only `source_file` and `run` are strictly required, and only for the **active**
language — an unused, partially-filled entry will not block commands that do not
use it.

---

## Command placeholders

`compile` and `run` are command templates. Two placeholders are substituted
before the command is executed:

| Placeholder | Replaced with |
|-------------|---------------|
| `{source}` | the value of `source_file` (e.g. `code.cpp`). |
| `{executable}` | the compiled binary — its **name** during compilation, and its **full path** when running. Empty for interpreted languages. |

Commands are tokenized safely, so paths containing spaces are handled correctly.

**Interpreted language** (`compile` is `null`): only `run` is used, e.g.
`python3 {source}` → `python3 code.py`.

**Compiled language**: `compile` runs first; if it returns non-zero (or no
binary is produced) the run is aborted with a compilation error. Otherwise `run`
executes, e.g. `compile: "g++ {source} -o {executable}"` then `run: "{executable}"`.

---

## Clearing and typing values

- The literal string `null` passed to `./cpt.py config <key> null` sets the field to JSON `null`.
- `set` coerces the new value to the existing field's type: booleans accept `true`/`false`/`1`/`0`/`yes`/`no`; integers must parse as integers; everything else is stored as a string. A field that is currently `null` is treated as a string going forward.

---

## Example

```json
{
  "contests_path": "/home/user/cp/contests",
  "language": "cpp",
  "editor": "code",
  "languages": {
    "cpp": {
      "extension": ".cpp",
      "source_file": "code.cpp",
      "template": "/home/user/cp/cptool/templates/template.cpp",
      "compile": "g++ -std=c++17 -Wall -Wextra -fsanitize=address,undefined {source} -o {executable}",
      "run": "{executable}",
      "executable": "code",
      "comment": "//"
    },
    "python": {
      "extension": ".py",
      "source_file": "code.py",
      "template": "/home/user/cp/cptool/templates/template.py",
      "compile": null,
      "run": "python3 {source}",
      "executable": null,
      "comment": "#"
    }
  }
}
```

---

## Validation rules

`config.json` is rejected at load time (with a `config.json: …` message) if:

- it is not valid JSON, or not a JSON object;
- any of `contests_path`, `language`, `languages` is missing;
- `contests_path` is not a non-empty string, or `language`/`editor` is not a string;
- `languages` is empty or not an object, or any entry is not an object;
- the active `language` has no entry under `languages`;
- the active language is missing `source_file` or `run`;
- the active language has a `compile` command but no `executable`;
- the active language's `source_file` or `executable` is not a bare filename (contains a path separator or is absolute).
