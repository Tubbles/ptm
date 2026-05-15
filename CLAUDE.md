# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PTM ("Python Text Manipulator") is a single-file CLI: a Unix-style line filter with subcommands. Each subcommand reads lines from positional `VAL` args or stdin (or generates them) and writes one result line to stdout. The whole project deliberately stays in `ptm.py` plus tests; a package layout would be over-engineering.

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
- Subcommands that consume input use `_lines_from(args.values)` in their dispatch lambda: this returns the positional `VAL` list when the user passed one, and `sys.stdin` otherwise. The cmd function itself just sees an `Iterable[str]`; it doesn't know or care which source filled it.
- `main()` calls `args.run(args)` and prints each yielded line. It is the only place that does stdout I/O. It also owns the trailing-newline policy described under "Conventions" below.

When adding a new subcommand:

1. Write the cmd function as a pure generator with a doctest.
2. Add a parser branch in `build_parser()` and a `run=lambda ...` that adapts the `Namespace` and (if needed) `sys.stdin` to the function's signature.
3. If the subcommand consumes lines, declare `sp.add_argument("values", nargs="*", metavar="VAL")` and route input through `_lines_from(a.values)` so callers can supply values on the command line *or* via stdin. Mention both styles in the subparser's `description=`, matching the wording used by `inc`/`dec`/`eval`. Without this the user gets the same hang/empty-help trap that motivated dual input in the first place: `ptm <new-cmd>` with no pipe just blocks on `sys.stdin` and `--help` is silent about it.
4. Add an end-to-end test in `tests/test_cli.py` using `capsys` and the `_set_stdin` helper. For input-consuming subcommands add a positional-args test too (no `_set_stdin` call) so a regression that ignores positional VALs hangs the test instead of silently passing.

If a cmd function would need `sys.stdin` directly, that is the signal you broke the purity invariant. Pass lines in as a parameter instead.

`_nonempty()` is the shared input-normalization helper: strip whitespace and drop empty lines. Use it in any cmd that reads input so blank-line behavior stays consistent across subcommands (and across the VAL/stdin split — a `ptm inc 1 '  5  '` invocation gets the same normalization as a piped `  5  ` line).

## Conventions specific to this repo

- `cmd_eval` evaluates each line with full builtins access on purpose; do not "harden" it with a restricted globals dict without asking. The whole point is to be a calculator over trusted input.
- `seq FIRST INCREMENT [NUM]` is **count-based**, not coreutils-style: `NUM` is the number of elements to emit, not an upper bound. `INCREMENT` may be any integer (including 0, which yields `NUM` copies of `FIRST`). Don't reintroduce a "must reach LAST" interpretation or a non-zero-increment validator without asking.
- `NUM` is optional. When omitted, `_seq_run` reads `MICRO_CURSOR_COUNT` and `MICRO_CURSOR_INDEX` from the environment and renders the single element at that index of the count-length sequence. The intended workflow is the micro editor running ptm once per cursor, each invocation getting a different `INDEX` in `[0, COUNT)`, so the full sequence is distributed across cursors. Explicit `NUM` takes precedence; env vars are only consulted when `args.num is None`. With padding, width is computed against the **full** `num`-element sequence (not just the indexed element) so parallel invocations align. The hardcoded `MICRO_*` prefix is intentional for now; if other editors need to drive this, generalize the env-var names rather than adding a second parallel mechanism.
- The trailing-newline policy is global, owned by `main()`, not per-subcommand. `main()` buffers one yielded line ahead so it can identify the *last* line, prints inter-line newlines unconditionally (they're what makes the output multi-line), and decides only the final `\n` from `args.newline` falling back to `sys.stdout.isatty()`. TTY (interactive shell) → trailing newline so the next prompt isn't smushed against the output. Non-TTY (any editor's textfilter — micro's `textfilter`, vim's `!` filter, emacs's `shell-command-on-region`, helix's `:pipe`, kakoune's `|`, etc. — or any shell pipe or redirect to file) → no trailing newline, because editor textfilter selections frequently don't include a trailing newline themselves and a stray `\n` would land in the buffer. The two early-version heuristics that lived in `_seq_run` (cursor-mode-only, and seq-only-isatty) didn't generalize: the partial-line-selection case dominates and applies to every subcommand, not just `seq`.
- The `-n` / `--newline` / `--no-newline` flag overrides the auto-detection when the heuristic guesses wrong (`ptm dec2hex 255 --newline | wc -l`, or `--no-newline` from a wrapper script that pipes back to a TTY). It's declared once on a `common = argparse.ArgumentParser(add_help=False)` parent parser and inherited via `parents=[common]` on every `sub.add_parser(...)` call, including the ones generated by the base-conversion loop. Don't redeclare the flag on individual subparsers — argparse will error on the duplicate, and even if it didn't, the per-subcommand declaration would drift from the parent. Don't move the buffer-one-line-ahead loop out of `main()` either: the cmd functions stay pure (`Iterator[str]`), and that's load-bearing for the doctests.
- About `-n`: echo(1) and printf(1) use `-n` for the *opposite* meaning (suppress newline). The help text calls this out explicitly. If the inversion ever feels too dangerous in practice, switch to long-form only (`--newline` / `--no-newline`) rather than picking some other short letter — the user knows `-n` and explicitly asked for it.
- Tests under `capsys` see the non-TTY path (CaptureIO's underlying BytesIO reports `isatty() = False`); the TTY path is covered by `test_*_tty_keeps_trailing_newline` tests via `monkeypatch.setattr(sys.stdout, "isatty", lambda: True)`. `test_every_subcommand_accepts_newline_flag` asserts the parent parser actually propagates to every registered subparser, so a missing `parents=[common]` in a future subcommand fails loudly.
- `_seq_die(msg)` is the seq-specific clean-exit helper. It writes `ptm seq: <msg>` to stderr and `sys.exit(2)`. Don't replace it with a bare `sys.exit(msg)` — that only writes to stderr when `SystemExit` propagates to the interpreter, so test harnesses (and `main()` callers that catch `SystemExit`) see no message.
- `seq` is the only subcommand whose CLI output diverges from its `cmd_*` shape: `cmd_seq` yields individual values (good for doctests and Python use), but the CLI dispatcher is `_seq_run`, which joins those values with spaces and yields one line back to `main()`. `_seq_run` also suppresses the empty case (no joined string → no yield), so `ptm seq 0 1 0` produces zero bytes — `main()`'s buffer-one-ahead loop sees an empty iterator and writes nothing. Don't replace `_seq_run` with an inline lambda just to "match" the other subcommands; the empty-suppression is the value-add.
- `seq` accepts mutually exclusive `-z` (zero left-pad) and `-p` (space left-pad) flags. Padding width is the width of the widest value in the sequence so columns line up. Zero-padding is sign-aware (uses `str.zfill`), so `-1 0 1` with `-z` becomes `-1 00 01`, never `0-1`. Don't replace `str.zfill` with `rjust(w, "0")` — it produces sign-eating garbage for negatives. The flag is `-z`, not `-0`: an option string matching argparse's negative-number regex (`^-\d+$`) flips `_has_negative_number_optionals` on and breaks negative positionals like `ptm seq -2 1 5`. Stay clear of `-0`, `-1`, `-2`, … as flag names anywhere in this CLI.
- Lambdas in `build_parser()` use `lambda _: ...` (Pyright accepts the bare-underscore discard) when the `Namespace` is unused. Don't reintroduce a uniform `(args, stdin)` signature on the cmd functions just to satisfy dispatch symmetry; it forced unused-parameter warnings before.
- All base-conversion subcommands (`bin2hex`, `dec2oct`, etc., 12 total) and the generic `baseconv FROM TO` share one implementation: `cmd_baseconv(from_base, to_base, lines)`. The 12 named ones are generated in a nested loop in `build_parser()` from the `_BASES` dict. The lambda inside the loop uses `lambda _, s=src_base, d=dst_base: ...` for default-arg capture; without that, every lambda would close over the final iteration's bases. Don't add separate `cmd_dec2hex`-style functions back; if a new named alias is needed, just add an entry to `_BASES`.
- Two digit alphabets, switched at base 36/37, deliberately discontinuous:
  - `_DIGITS_LOW = "0..9a..z"` (36 chars) for bases 2..36. Keeps hex/oct/etc. behaving the way users expect (`ff` is hex 255).
  - `_DIGITS_HIGH = string.ascii_uppercase + string.ascii_lowercase + string.digits + "+/"` (64 chars, RFC 4648 §4) for bases 37..64.
  Don't merge them. RFC 4648 ordering at low bases would make `_to_base(10, 16)` emit `'K'` instead of `'a'`, breaking every hex doctest and CLI call. The discontinuity is also why `_to_base(0, 64) == 'A'` (not `'0'`) — the zero short-circuit returns `alphabet[0]`, not the literal char `'0'`.
- `_from_base` has two regimes for the same reason: bases 2..36 delegate to stdlib `int(s, base)` so mixed case keeps working (`hex2dec FF` and `hex2dec ff` both yield 255); bases 37..64 use a case-sensitive walk over `_DIGITS_HIGH`. Don't try to unify the two paths by always lowercasing input — that would silently corrupt base-37+ values.
- `baseconv` is **positional numeric conversion**, not binary-stream encoding. Even at base 64 with the RFC 4648 alphabet, it does not produce the same output as `base64(1)` for the same bytes: it has no byte-grouping, no `=` padding, and accepts only ASCII numerals on stdin. Don't "fix" this by adding padding or 24-bit framing. If a real base64 encoder is ever wanted, it should be a separate subcommand reading bytes, not a tweak to `cmd_baseconv`.
