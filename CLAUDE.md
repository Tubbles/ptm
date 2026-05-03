# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PTM ("Python Text Manipulator") is a single-file CLI: a Unix-style line filter with subcommands. Each subcommand reads lines from stdin (or generates them) and writes one result line to stdout. The whole project deliberately stays in `ptm.py` plus tests; a package layout would be over-engineering.

Python `>=3.13` is required. The codebase uses PEP 695 `type` aliases and modern stdlib generics, so don't try to back-port to older Pythons without removing those features.

## Commands

```sh
uv venv                                                       # create .venv
uv pip install --python .venv/bin/python pytest ruff          # dev tools
.venv/bin/python -m pytest                                    # all tests + doctests
.venv/bin/python -m pytest tests/test_cli.py::test_inc -v     # single test
.venv/bin/python -m pytest --doctest-modules ptm.py           # doctests only
.venv/bin/ruff check .                                        # lint
.venv/bin/ruff format .                                       # format
```

`addopts = "--doctest-modules"` is set in `pyproject.toml`, so plain `pytest` collects both `tests/` and the doctests inside `ptm.py`. Don't add a separate doctest script.

## Architecture

The dispatch shape is the only non-obvious thing in the file:

- Each `cmd_*` function is **pure**: it takes its primitive arguments and (where relevant) an `Iterable[str]` of input lines, and returns an `Iterator[str]` of output lines. No `argparse.Namespace` coupling, no `sys.stdin`/`sys.stdout` reads, no `print`. This is what makes them trivially doctestable with literal lists.
- `build_parser()` wires each subcommand to a `run` lambda stored via `set_defaults(run=...)`. The lambda is the only place that touches `sys.stdin` and unpacks the `Namespace` into the cmd function's real arguments. Argparse stays at the edge.
- `main()` calls `args.run(args)` and prints each yielded line. It is the only place that does I/O.

When adding a new subcommand:

1. Write the cmd function as a pure generator with a doctest.
2. Add a parser branch in `build_parser()` and a `run=lambda ...` that adapts the `Namespace` and (if needed) `sys.stdin` to the function's signature.
3. Add an end-to-end test in `tests/test_cli.py` using `capsys` and the `_set_stdin` helper.

If a cmd function would need `sys.stdin` directly, that is the signal you broke the purity invariant. Pass lines in as a parameter instead.

`_nonempty()` is the shared input-normalization helper: strip whitespace and drop empty lines. Use it in any cmd that reads stdin so blank-line behavior stays consistent across subcommands.

## Conventions specific to this repo

- `cmd_eval` evaluates each line with full builtins access on purpose; do not "harden" it with a restricted globals dict without asking. The whole point is to be a calculator over trusted input.
- `seq FIRST INCREMENT NUM` is **count-based**, not coreutils-style: `NUM` is the number of elements to emit, not an upper bound. `INCREMENT` may be any integer (including 0, which yields `NUM` copies of `FIRST`). Don't reintroduce a "must reach LAST" interpretation or a non-zero-increment validator without asking.
- `seq` is the only subcommand whose CLI output diverges from its `cmd_*` shape: `cmd_seq` yields individual values (good for doctests and Python use), but the CLI dispatcher is `_seq_run`, which joins those values with spaces and emits one line. `_seq_run` also suppresses the empty case (no joined string → no yield), so `ptm seq 0 1 0` produces zero bytes, not a stray newline. Don't replace `_seq_run` with an inline lambda just to "match" the other subcommands; the empty-suppression and the comment are the value-add.
- Lambdas in `build_parser()` use `lambda _: ...` (Pyright accepts the bare-underscore discard) when the `Namespace` is unused. Don't reintroduce a uniform `(args, stdin)` signature on the cmd functions just to satisfy dispatch symmetry; it forced unused-parameter warnings before.
- All base-conversion subcommands (`bin2hex`, `dec2oct`, etc., 12 total) and the generic `baseconv FROM TO` share one implementation: `cmd_baseconv(from_base, to_base, lines)`. The 12 named ones are generated in a nested loop in `build_parser()` from the `_BASES` dict. The lambda inside the loop uses `lambda _, s=src_base, d=dst_base: ...` for default-arg capture; without that, every lambda would close over the final iteration's bases. Don't add separate `cmd_dec2hex`-style functions back; if a new named alias is needed, just add an entry to `_BASES`.
- Two digit alphabets, switched at base 36/37, deliberately discontinuous:
  - `_DIGITS_LOW = "0..9a..z"` (36 chars) for bases 2..36. Keeps hex/oct/etc. behaving the way users expect (`ff` is hex 255).
  - `_DIGITS_HIGH = string.ascii_uppercase + string.ascii_lowercase + string.digits + "+/"` (64 chars, RFC 4648 §4) for bases 37..64.
  Don't merge them. RFC 4648 ordering at low bases would make `_to_base(10, 16)` emit `'K'` instead of `'a'`, breaking every hex doctest and CLI call. The discontinuity is also why `_to_base(0, 64) == 'A'` (not `'0'`) — the zero short-circuit returns `alphabet[0]`, not the literal char `'0'`.
- `_from_base` has two regimes for the same reason: bases 2..36 delegate to stdlib `int(s, base)` so mixed case keeps working (`hex2dec FF` and `hex2dec ff` both yield 255); bases 37..64 use a case-sensitive walk over `_DIGITS_HIGH`. Don't try to unify the two paths by always lowercasing input — that would silently corrupt base-37+ values.
- `baseconv` is **positional numeric conversion**, not binary-stream encoding. Even at base 64 with the RFC 4648 alphabet, it does not produce the same output as `base64(1)` for the same bytes: it has no byte-grouping, no `=` padding, and accepts only ASCII numerals on stdin. Don't "fix" this by adding padding or 24-bit framing. If a real base64 encoder is ever wanted, it should be a separate subcommand reading bytes, not a tweak to `cmd_baseconv`.
