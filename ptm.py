#!/usr/bin/env python3
"""ptm: Python Text Manipulator.

A small Unix-style filter with subcommands. Each subcommand reads lines from
stdin (or generates them) and writes one result line to stdout, so commands
compose naturally with pipes:

    $ printf '1\\n2\\n3\\n' | ptm inc 10
    11
    12
    13

    $ ptm seq 0 2 3
    0 2 4

    $ printf '255\\n4096\\n' | ptm dec2hex
    ff
    1000

    $ printf '1010\\n11111111\\n' | ptm baseconv 2 16
    a
    ff

    $ printf '1+2\\n7*8\\n2**10\\n' | ptm eval
    3
    56
    1024
"""

import argparse
import os
import string
import sys
from collections.abc import Iterable, Iterator
from typing import Final, NoReturn

__all__ = [
    "build_parser",
    "cmd_baseconv",
    "cmd_dec",
    "cmd_eval",
    "cmd_inc",
    "cmd_seq",
    "main",
]

__version__: Final[str] = "0.1.0"

type Lines = Iterable[str]

_BASES: Final[dict[str, int]] = {"bin": 2, "oct": 8, "dec": 10, "hex": 16}
# Two alphabets, switched at base 36/37:
#   - `_DIGITS_LOW` keeps the conventional digits-first ordering so that hex,
#     oct, and every other base ≤ 36 behaves the way users expect (`ff` is 255
#     in base 16, `z` is 35 in base 36).
#   - `_DIGITS_HIGH` is the RFC 4648 base64 alphabet (uppercase first, then
#     lowercase, then digits, then `+/`), used for bases 37..64. The two
#     alphabets are intentionally discontinuous: in `_DIGITS_HIGH` the char
#     `'0'` represents the value 52 and `'A'` represents 0, so a string like
#     `"10"` parsed at base 64 does NOT mean sixty-four.
_DIGITS_LOW: Final[str] = string.digits + string.ascii_lowercase  # 36 chars
_DIGITS_HIGH: Final[str] = (
    string.ascii_uppercase + string.ascii_lowercase + string.digits + "+/"
)  # 64 chars, RFC 4648 §4
_MAX_BASE: Final[int] = len(_DIGITS_HIGH)  # 64


def _nonempty(lines: Lines) -> Iterator[str]:
    """Yield each input line stripped of surrounding whitespace, dropping empties.

    >>> list(_nonempty(["a", "  ", "b\\n", ""]))
    ['a', 'b']
    """
    for line in lines:
        s = line.strip()
        if s:
            yield s


def cmd_inc(amount: int, lines: Lines) -> Iterator[str]:
    """Add `amount` to each integer line.

    >>> list(cmd_inc(1, ["1", "2", "10"]))
    ['2', '3', '11']
    >>> list(cmd_inc(-3, ["10", " 5 ", ""]))
    ['7', '2']
    """
    for line in _nonempty(lines):
        yield str(int(line) + amount)


def cmd_dec(amount: int, lines: Lines) -> Iterator[str]:
    """Subtract `amount` from each integer line.

    >>> list(cmd_dec(1, ["10", "5", "1"]))
    ['9', '4', '0']
    >>> list(cmd_dec(-3, ["10", " 5 ", ""]))
    ['13', '8']
    """
    for line in _nonempty(lines):
        yield str(int(line) - amount)


def cmd_eval(lines: Lines) -> Iterator[str]:
    """Evaluate each line as a Python expression and yield the str of its result.

    The expression is evaluated with full access to Python builtins; this is
    intentional (it is the point of the command) but means input must be
    trusted.

    >>> list(cmd_eval(["1+2", "7*8", "2**10"]))
    ['3', '56', '1024']
    >>> list(cmd_eval(["len('hello')"]))
    ['5']
    """
    for line in _nonempty(lines):
        yield str(eval(line))


def cmd_seq(
    first: int,
    increment: int,
    num: int,
    *,
    pad: str = "",
    index: int | None = None,
) -> Iterator[str]:
    """Yield elements of an arithmetic sequence starting at `first`.

    `num` is the sequence length, a count rather than an upper bound:
    `cmd_seq(0, 2, 3)` yields 0, 2, 4. `increment` may be any integer; zero
    yields `num` copies of `first`, negative values descend. A non-positive
    `num` yields an empty sequence.

    `pad` is `""` (no padding, default), `"0"` for zero left-padding, or `" "`
    for space left-padding. When set, all values are padded to the width of
    the widest value in the **full** `num`-element sequence so they line up.
    Zero-padding is sign-aware (matches `str.zfill`): `-1` next to `100`
    becomes `-001`, not `0-01`.

    `index`, when set, restricts output to the single element at that
    position in the sequence (`first + index*increment`). The padding width
    is still computed against the full `num`-element sequence, so multiple
    parallel invocations rendering different indices line up. `index` must
    be in `[0, num)`; otherwise `ValueError`.

    >>> list(cmd_seq(0, 2, 3))
    ['0', '2', '4']
    >>> list(cmd_seq(0, 1, 5))
    ['0', '1', '2', '3', '4']
    >>> list(cmd_seq(10, -2, 4))
    ['10', '8', '6', '4']
    >>> list(cmd_seq(7, 0, 3))
    ['7', '7', '7']
    >>> list(cmd_seq(0, 1, 0))
    []
    >>> list(cmd_seq(8, 1, 3, pad="0"))
    ['08', '09', '10']
    >>> list(cmd_seq(8, 1, 3, pad=" "))
    [' 8', ' 9', '10']
    >>> list(cmd_seq(-1, 1, 3, pad="0"))
    ['-1', '00', '01']
    >>> list(cmd_seq(-1, 1, 3, pad=" "))
    ['-1', ' 0', ' 1']
    >>> list(cmd_seq(-2, 1, 4, pad="0"))
    ['-2', '-1', '00', '01']
    >>> list(cmd_seq(0, 1, 0, pad="0"))
    []
    >>> list(cmd_seq(0, 1, 5, index=0))
    ['0']
    >>> list(cmd_seq(0, 1, 5, index=4))
    ['4']
    >>> list(cmd_seq(1, 1, 10, pad="0", index=0))
    ['01']
    >>> list(cmd_seq(1, 1, 10, pad="0", index=9))
    ['10']
    >>> list(cmd_seq(0, 1, 5, index=5))
    Traceback (most recent call last):
        ...
    ValueError: index 5 out of range for sequence of length 5
    """
    if index is not None and not 0 <= index < num:
        raise ValueError(f"index {index} out of range for sequence of length {num}")
    if not pad:
        if index is not None:
            yield str(first + index * increment)
            return
        n = first
        for _ in range(num):
            yield str(n)
            n += increment
        return
    if num <= 0:
        return
    values = [str(first + i * increment) for i in range(num)]
    width = max(len(v) for v in values)
    # `str.zfill` keeps the sign at the front and pads zeros after it,
    # matching Python's `f"{-1:03d}" == "-01"`. Plain `rjust(width, "0")`
    # would emit `"0-1"`, which no one wants.
    pad_one = (lambda v: v.zfill(width)) if pad == "0" else (lambda v: v.rjust(width, pad))
    if index is not None:
        yield pad_one(values[index])
    else:
        for v in values:
            yield pad_one(v)


def _seq_run(args: argparse.Namespace) -> Iterator[str]:
    """CLI adapter: join `cmd_seq`'s values into one space-separated line.

    The CLI presentation for `seq` is intentionally one-line-with-spaces (so
    it pipes to tools like `xargs` or shell `for` loops without rewriting),
    while `cmd_seq` itself keeps yielding individual values for Python use
    and doctests. An empty sequence yields nothing here, so empty output
    stays truly empty rather than emitting a stray newline.

    If `NUM` was omitted on the CLI, this reads `MICRO_CURSOR_COUNT` and
    `MICRO_CURSOR_INDEX` from the environment: one ptm invocation per
    cursor, each invocation gets a different `INDEX` in `[0, COUNT)`, and
    we emit just that cursor's element of the `COUNT`-length sequence.
    Padding width is computed against the full sequence so parallel
    invocations align.
    """
    num = args.num
    index: int | None = None
    if num is None:
        try:
            num = int(os.environ["MICRO_CURSOR_COUNT"])
            index = int(os.environ["MICRO_CURSOR_INDEX"])
        except KeyError as e:
            _seq_die(f"NUM omitted and ${e.args[0]} is not set")
        except ValueError as e:
            _seq_die(f"env var must be an integer ({e})")
    try:
        line = " ".join(cmd_seq(args.first, args.increment, num, pad=args.pad or "", index=index))
    except ValueError as e:
        _seq_die(str(e))
    if line:
        yield line


def _seq_die(msg: str) -> NoReturn:
    """Write a clean error to stderr and exit. `sys.exit(msg)` alone only
    writes the message when SystemExit propagates to the interpreter, which
    isn't what test harnesses (or `main()` callers) see."""
    print(f"ptm seq: {msg}", file=sys.stderr)
    sys.exit(2)


def _to_base(n: int, base: int) -> str:
    """Format `n` as a string in `base` (2..64).

    Bases 2..36 use the conventional `0..9a..z` alphabet. Bases 37..64 use
    the RFC 4648 base64 alphabet (`A..Za..z0..9+/`); note the discontinuity
    at the boundary, which is intentional so hex et al. keep working.

    >>> _to_base(255, 16)
    'ff'
    >>> _to_base(10, 2)
    '1010'
    >>> _to_base(0, 2)
    '0'
    >>> _to_base(-10, 2)
    '-1010'
    >>> _to_base(35, 36)
    'z'
    >>> _to_base(0, 64)
    'A'
    >>> _to_base(36, 64)
    'k'
    >>> _to_base(63, 64)
    '/'
    >>> _to_base(64, 64)
    'BA'
    """
    if not 2 <= base <= _MAX_BASE:
        raise ValueError(f"base must be in 2..{_MAX_BASE}, got {base}")
    alphabet = _DIGITS_LOW if base <= 36 else _DIGITS_HIGH
    if n == 0:
        return alphabet[0]
    sign = "-" if n < 0 else ""
    n = abs(n)
    digits: list[str] = []
    while n:
        digits.append(alphabet[n % base])
        n //= base
    return sign + "".join(reversed(digits))


def _from_base(s: str, base: int) -> int:
    """Parse `s` as an integer in `base` (2..64).

    For bases 2..36 we delegate to stdlib `int(s, base)` so the long-standing
    case-insensitive convention (`int("FF", 16) == 255`) is preserved. For
    bases 37..64 the parser is case-sensitive against the RFC 4648 alphabet,
    where `'A'` is digit 0 and `'0'` is digit 52.

    >>> _from_base("ff", 16)
    255
    >>> _from_base("FF", 16)
    255
    >>> _from_base("A", 64)
    0
    >>> _from_base("/", 64)
    63
    >>> _from_base("BA", 64)
    64
    >>> _from_base("10", 64)
    3444
    >>> _from_base("-/", 64)
    -63
    """
    if not 2 <= base <= _MAX_BASE:
        raise ValueError(f"base must be in 2..{_MAX_BASE}, got {base}")
    if base <= 36:
        return int(s, base)
    s = s.strip()
    sign = 1
    if s.startswith(("-", "+")):
        sign = -1 if s[0] == "-" else 1
        s = s[1:]
    if not s:
        raise ValueError(f"empty number for base {base}")
    n = 0
    for ch in s:
        idx = _DIGITS_HIGH.find(ch)
        if idx < 0 or idx >= base:
            raise ValueError(f"invalid digit {ch!r} for base {base}")
        n = n * base + idx
    return sign * n


def _base_int(s: str) -> int:
    n = int(s)
    if not 2 <= n <= _MAX_BASE:
        raise argparse.ArgumentTypeError(f"must be in 2..{_MAX_BASE}")
    return n


def cmd_baseconv(from_base: int, to_base: int, lines: Lines) -> Iterator[str]:
    """Convert each integer line from `from_base` to `to_base` (each in 2..64).

    Bases 2..36 use the conventional `0..9a..z` alphabet and accept mixed
    case (delegating to stdlib `int`). Bases 37..64 use the RFC 4648 base64
    alphabet `A..Za..z0..9+/` and are case-sensitive. Zero and negatives
    pass through.

    >>> list(cmd_baseconv(10, 16, ["255", "4096"]))
    ['ff', '1000']
    >>> list(cmd_baseconv(2, 16, ["1010", "11111111"]))
    ['a', 'ff']
    >>> list(cmd_baseconv(16, 2, ["ff", "10"]))
    ['11111111', '10000']
    >>> list(cmd_baseconv(8, 10, ["77", "10"]))
    ['63', '8']
    >>> list(cmd_baseconv(10, 10, ["42"]))
    ['42']
    >>> list(cmd_baseconv(10, 64, ["0", "63", "64", "4096"]))
    ['A', '/', 'BA', 'BAA']
    >>> list(cmd_baseconv(64, 10, ["A", "/", "BA", "BAA"]))
    ['0', '63', '64', '4096']
    """
    for line in _nonempty(lines):
        yield _to_base(_from_base(line, from_base), to_base)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ptm", description="Python Text Manipulator")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("inc", help="Add N to each integer on stdin")
    sp.add_argument("amount", type=int)
    sp.set_defaults(run=lambda a: cmd_inc(a.amount, sys.stdin))

    sp = sub.add_parser("dec", help="Subtract N from each integer on stdin")
    sp.add_argument("amount", type=int)
    sp.set_defaults(run=lambda a: cmd_dec(a.amount, sys.stdin))

    sp = sub.add_parser("eval", help="Evaluate each line on stdin as a Python expression")
    sp.set_defaults(run=lambda _: cmd_eval(sys.stdin))

    sp = sub.add_parser(
        "seq",
        help=(
            "Print NUM elements starting at FIRST, stepping by INCREMENT, "
            "or one element per multi-cursor invocation if NUM is omitted"
        ),
        description=(
            "Print NUM elements starting at FIRST, stepping by INCREMENT, "
            "as a single space-separated line. If NUM is omitted, the env "
            "vars MICRO_CURSOR_COUNT and MICRO_CURSOR_INDEX (set by the "
            "editor when the same command runs once per cursor) select the "
            "sequence length and which single element this invocation "
            "emits, distributing the sequence across cursors. An explicit "
            "NUM takes precedence over the env vars."
        ),
    )
    pad_group = sp.add_mutually_exclusive_group()
    pad_group.add_argument(
        "-z",
        dest="pad",
        action="store_const",
        const="0",
        help="Left-pad each value with zeros so all values line up (sign-aware)",
    )
    pad_group.add_argument(
        "-p",
        dest="pad",
        action="store_const",
        const=" ",
        help="Left-pad each value with spaces so all values line up",
    )
    sp.add_argument("first", type=int)
    sp.add_argument("increment", type=int)
    sp.add_argument("num", type=int, nargs="?", default=None)
    sp.set_defaults(run=_seq_run, pad=None)

    for src_name, src_base in _BASES.items():
        for dst_name, dst_base in _BASES.items():
            if src_name == dst_name:
                continue
            sp = sub.add_parser(
                f"{src_name}2{dst_name}",
                help=f"Convert each {src_name} integer on stdin to {dst_name}",
            )
            # Default-arg capture binds the loop values; without `s=` and `d=`
            # every lambda would close over the final iteration's bases.
            sp.set_defaults(run=lambda _, s=src_base, d=dst_base: cmd_baseconv(s, d, sys.stdin))

    sp = sub.add_parser(
        "baseconv",
        help="Convert each integer on stdin from base FROM to base TO (each in 2..36)",
    )
    sp.add_argument("from_base", metavar="FROM", type=_base_int)
    sp.add_argument("to_base", metavar="TO", type=_base_int)
    sp.set_defaults(run=lambda a: cmd_baseconv(a.from_base, a.to_base, sys.stdin))

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    for line in args.run(args):
        print(line)


if __name__ == "__main__":
    main()
