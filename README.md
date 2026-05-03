# Python Text Manipulator

A tiny Unix-style filter with subcommands. Each subcommand reads lines from stdin (or generates them) and writes one result line to stdout, so commands compose naturally with pipes.

## Usage

```sh
$ printf '1\n2\n3\n' | ptm inc 10
11
12
13

$ ptm seq 0 2 3
0 2 4

$ printf '255\n4096\n' | ptm dec2hex
ff
1000

$ printf '1010\n11111111\n' | ptm baseconv 2 16
a
ff

$ printf '1+2\n7*8\n2**10\n' | ptm eval
3
56
1024
```

`ptm eval` evaluates each line as a Python expression with full access to builtins. Treat it as a calculator over trusted input.

## Subcommands

| Command                | Reads stdin? | Description                                                      |
| ---------------------- | :----------: | ---------------------------------------------------------------- |
| `inc N`                | yes          | Add `N` (may be negative) to each integer line.                  |
| `dec N`                | yes          | Subtract `N` (may be negative) from each integer line.           |
| `eval`                 | yes          | Evaluate each line as a Python expression.                       |
| `seq FIRST INC NUM`    | no           | Print `NUM` elements starting at `FIRST`, stepping by `INC` (any integer, including 0 or negative), as one space-separated line. |
| `bin2oct`, `bin2dec`, `bin2hex`, `oct2bin`, `oct2dec`, `oct2hex`, `dec2bin`, `dec2oct`, `dec2hex`, `hex2bin`, `hex2oct`, `hex2dec` | yes | Pairwise base-conversion shortcuts among `bin` (base 2), `oct` (8), `dec` (10), `hex` (16). |
| `baseconv FROM TO`     | yes          | Generic version for arbitrary bases (each in `2..64`). E.g. `baseconv 2 16` is `bin2hex`. Bases 2..36 use the conventional `0..9a..z` alphabet (case-insensitive). Bases 37..64 switch to the RFC 4648 base64 alphabet `A..Za..z0..9+/` (case-sensitive), so `'A'` is digit 0 and `'0'` is digit 52. The alphabets are deliberately discontinuous at the boundary so hex et al. keep their familiar form. |

`baseconv` is positional numeric conversion only. Even at base 64 it is *not* interoperable with `base64(1)` / RFC 4648 binary-to-text encoding: it shares the alphabet (above 36), not the byte-stream framing or `=` padding.

Blank and whitespace-only lines on stdin are skipped silently.

## Install

`ptm.py` is a single-file script with no third-party dependencies, so a copy or symlink into `/usr/local/bin` is enough. Python `>=3.13` must be on `PATH` as `python3` (the shebang resolves it via `env`).

Copy (snapshot the current script):

```sh
sudo install -m 755 ptm.py /usr/local/bin/ptm
```

Symlink (so future edits in this checkout take effect immediately):

```sh
sudo ln -sf "$(pwd)/ptm.py" /usr/local/bin/ptm
```

Verify:

```sh
ptm seq 0 2 3
```

To uninstall:

```sh
sudo rm /usr/local/bin/ptm
```

## Development

Requires Python `>=3.13`. Set up a venv with `uv` and install the dev tools:

```sh
uv venv
uv pip install --python .venv/bin/python -e . --group dev
```

Run the test suite (CLI tests in `tests/` plus doctests collected from `ptm.py`):

```sh
.venv/bin/python -m pytest
```

Lint and format:

```sh
.venv/bin/ruff check .
.venv/bin/ruff format .
```

## License

[GNU Affero General Public License v3.0 or later](LICENSE) (AGPL-3.0-or-later).
