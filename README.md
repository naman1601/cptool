# cptool

A command-line tool for competitive programming. cptool downloads problems from [Competitive Companion](https://github.com/jmerle/competitive-companion) — including testcases and time/memory limits — into an organized directory tree, and tests solutions against those testcases.

cptool recognizes Codeforces, AtCoder, CodeChef, CSES, and USACO, filing their problems by contest and problem code (for example, `codeforces/1850/a/`). Problems from other sources are downloaded too, under `unknown/<problem-name>/`.

## Setup

cptool requires Python 3.10+ and the [Competitive Companion](https://github.com/jmerle/competitive-companion) browser extension.

```bash
pip install -r requirements.txt
./cpt.py init
```

`init` prompts for an editor, a default language, and a contests directory, then writes `config.json` and seeds starter templates into `templates/`.

## Usage

| Command | Description |
|---------|-------------|
| `cpt.py` | Listen for Competitive Companion and create the problem folder(s). |
| `cpt.py t` | Test the current directory's solution against `in*.txt` / `ans*.txt`. |
| `cpt.py g` | Generate a solution file from the configured template. |
| `cpt.py e` | Echo the raw Competitive Companion payload and exit. |
| `cpt.py init` | Re-run the configuration wizard. |
| `cpt.py config [<key>] [<value>]` | View or set configuration. |
| `cpt.py config add-language` | Add a language interactively. |

Downloading a problem writes its testcases, seeds a solution file from the configured template, and opens it in the editor.

Testing compiles the solution if the language needs it, runs each `in<N>.txt`, and compares the output against `ans<N>.txt` (trailing whitespace ignored). A wrong answer prints the input, expected output, and actual output; a crash is reported per testcase without stopping the others; a compile error stops the run.

## Configuration

`config.json` lives next to the script. Edit it directly, or use `cpt.py config` with dotted keys for nesting (for example, `cpt.py config languages.cpp.run`). [CONFIG.md](CONFIG.md) documents every field with an example.

## Credits

cptool uses [Competitive Companion](https://github.com/jmerle/competitive-companion) for problem data, adapting its listener from [ecnerwala's script](https://gist.github.com/ecnerwala/ffc9b8c3f61e87ca043393a135d7794d).
