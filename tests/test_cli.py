"""End-to-end CLI tests for ptm.

These exercise `ptm.main(argv)` with monkeypatched stdin and assert on captured
stdout. Per-function unit tests are covered by the doctests in `ptm.py` and
collected by pytest via `--doctest-modules`.

Note on trailing newlines: `capsys` replaces stdout with a non-TTY CaptureIO,
so `main()`'s auto-detection suppresses the trailing newline on the final
yielded line. Inter-line newlines are always present. The TTY path is covered
by `test_*_tty_keeps_trailing_newline` tests via
`monkeypatch.setattr(sys.stdout, "isatty", ...)`.
"""

import argparse
import io
import sys

import pytest

import ptm


def _set_stdin(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def test_inc(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "1\n2\n10\n")
    ptm.main(["inc", "1"])
    assert capsys.readouterr().out == "2\n3\n11"


def test_inc_negative(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "100\n0\n")
    ptm.main(["inc", "-5"])
    assert capsys.readouterr().out == "95\n-5"


def test_inc_skips_blank_lines(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_stdin(monkeypatch, "1\n\n  \n2\n")
    ptm.main(["inc", "10"])
    assert capsys.readouterr().out == "11\n12"


def test_inc_positional(capsys: pytest.CaptureFixture[str]) -> None:
    # Values may be passed as positional args instead of stdin. No _set_stdin:
    # if positional args weren't honored, this test would hang on the real
    # sys.stdin (test harness would time out), so passing == correct dispatch.
    ptm.main(["inc", "1", "5", "6", "7"])
    assert capsys.readouterr().out == "6\n7\n8"


def test_inc_positional_negative_value(capsys: pytest.CaptureFixture[str]) -> None:
    # A leading `-5` must be treated as a positional value, not an option.
    # The inc subparser defines no negative-number-looking flags, so argparse
    # leaves the negative-number-optional regex unset and `-5` parses cleanly.
    ptm.main(["inc", "1", "-5", "10"])
    assert capsys.readouterr().out == "-4\n11"


def test_inc_positional_overrides_stdin(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Codifies the dispatch contract: when positional values are given,
    # stdin is ignored entirely (not concatenated, not appended).
    _set_stdin(monkeypatch, "100\n200\n")
    ptm.main(["inc", "1", "5"])
    assert capsys.readouterr().out == "6"


def test_inc_tty_keeps_trailing_newline(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The TTY → trailing-newline behavior is centralized in `main()` and
    # generalizes to every subcommand, not just `seq`. Pick `inc` as a
    # representative non-seq subcommand to lock that in.
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    ptm.main(["inc", "1", "5", "6"])
    assert capsys.readouterr().out == "6\n7\n"


def test_inc_newline_flag_forces_trailing_newline(capsys: pytest.CaptureFixture[str]) -> None:
    # The `-n` / `--newline` flag is declared on a shared parent parser, so
    # it's accepted by every subcommand. capsys → non-TTY, default suppresses;
    # the flag overrides.
    ptm.main(["inc", "--newline", "1", "5", "6"])
    assert capsys.readouterr().out == "6\n7\n"


def test_inc_no_newline_flag_suppresses_in_tty(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    ptm.main(["inc", "--no-newline", "1", "5", "6"])
    assert capsys.readouterr().out == "6\n7"


def test_inc_short_n_flag_is_force_on(capsys: pytest.CaptureFixture[str]) -> None:
    # Documents the deliberate inversion from echo(1)/printf(1): here `-n`
    # *adds* a trailing newline rather than suppressing one.
    ptm.main(["inc", "-n", "1", "5", "6"])
    assert capsys.readouterr().out == "6\n7\n"


def test_dec(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "10\n5\n1\n")
    ptm.main(["dec", "1"])
    assert capsys.readouterr().out == "9\n4\n0"


def test_dec_negative(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "10\n0\n")
    ptm.main(["dec", "-5"])
    assert capsys.readouterr().out == "15\n5"


def test_dec_positional(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["dec", "1", "10", "5"])
    assert capsys.readouterr().out == "9\n4"


def test_eval(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "1+2\n2**10\n")
    ptm.main(["eval"])
    assert capsys.readouterr().out == "3\n1024"


def test_eval_positional(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["eval", "1+2", "7*8", "2**10"])
    assert capsys.readouterr().out == "3\n56\n1024"


def test_seq_ascending(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "0", "2", "3"])
    assert capsys.readouterr().out == "0 2 4"


def test_seq_descending(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "10", "-2", "4"])
    assert capsys.readouterr().out == "10 8 6 4"


def test_seq_zero_increment_repeats(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "7", "0", "3"])
    assert capsys.readouterr().out == "7 7 7"


def test_seq_single_element_has_no_separator(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "42", "1", "1"])
    assert capsys.readouterr().out == "42"


def test_seq_zero_count_is_empty(capsys: pytest.CaptureFixture[str]) -> None:
    # Empty sequence must produce zero bytes of output, so a `read` from a
    # script can distinguish "empty" from "blank line".
    ptm.main(["seq", "0", "1", "0"])
    assert capsys.readouterr().out == ""


def test_seq_negative_count_is_empty(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "0", "1", "-3"])
    assert capsys.readouterr().out == ""


def test_seq_zero_pad(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "-z", "8", "1", "3"])
    assert capsys.readouterr().out == "08 09 10"


def test_seq_space_pad(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "-p", "8", "1", "3"])
    assert capsys.readouterr().out == " 8  9 10"


def test_seq_zero_pad_with_negatives_is_sign_aware(capsys: pytest.CaptureFixture[str]) -> None:
    # `-1` is two chars; zero-padded `0` and `1` must become `00`/`01`, not
    # something silly like `0-1`. Matches `str.zfill` / `f"{n:03d}"`.
    ptm.main(["seq", "-z", "-1", "1", "3"])
    assert capsys.readouterr().out == "-1 00 01"


def test_seq_space_pad_with_negatives(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "-p", "-1", "1", "3"])
    assert capsys.readouterr().out == "-1  0  1"


def test_seq_tty_keeps_trailing_newline(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Interactive terminal use: stdout reports as a TTY, so `main()` adds the
    # trailing newline. Without that, the shell prompt would smush against
    # the output.
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    ptm.main(["seq", "0", "1", "3"])
    assert capsys.readouterr().out == "0 1 2\n"


def test_seq_newline_flag_forces_trailing_newline(capsys: pytest.CaptureFixture[str]) -> None:
    # capsys is non-TTY; default behavior would suppress the newline. The
    # flag overrides that so the output is line-oriented (e.g. for `wc -l`).
    ptm.main(["seq", "--newline", "0", "1", "3"])
    assert capsys.readouterr().out == "0 1 2\n"


def test_seq_no_newline_flag_suppresses_in_tty(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    ptm.main(["seq", "--no-newline", "0", "1", "3"])
    assert capsys.readouterr().out == "0 1 2"


def test_seq_newline_flag_with_empty_sequence_emits_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # `--newline` adds the newline to *existing* output; it doesn't manufacture
    # output from nothing. An empty sequence stays empty either way, so
    # callers can still distinguish "no result" from "blank line".
    ptm.main(["seq", "--newline", "0", "1", "0"])
    assert capsys.readouterr().out == ""


def test_seq_pad_flags_are_mutually_exclusive(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        ptm.main(["seq", "-z", "-p", "1", "1", "3"])
    assert "not allowed with" in capsys.readouterr().err


def test_seq_zero_pad_empty_sequence_emits_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "-z", "0", "1", "0"])
    assert capsys.readouterr().out == ""


def test_seq_num_omitted_reads_cursor_env(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """One invocation per cursor. Each gets a different MICRO_CURSOR_INDEX
    and emits exactly that cursor's element of the full sequence."""
    monkeypatch.setenv("MICRO_CURSOR_COUNT", "5")
    monkeypatch.setenv("MICRO_CURSOR_INDEX", "0")
    ptm.main(["seq", "1", "1"])
    assert capsys.readouterr().out == "1"

    monkeypatch.setenv("MICRO_CURSOR_INDEX", "4")
    ptm.main(["seq", "1", "1"])
    assert capsys.readouterr().out == "5"


def test_seq_num_omitted_with_zero_pad_uses_full_sequence_width(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # COUNT=10 means the widest element ("10") is two chars, so the first
    # cursor's "1" must render as "01" to line up with siblings rendering
    # "02", ..., "10". This is the load-bearing reason cmd_seq computes
    # width against the full sequence rather than the indexed element only.
    monkeypatch.setenv("MICRO_CURSOR_COUNT", "10")
    monkeypatch.setenv("MICRO_CURSOR_INDEX", "0")
    ptm.main(["seq", "-z", "1", "1"])
    assert capsys.readouterr().out == "01"

    monkeypatch.setenv("MICRO_CURSOR_INDEX", "9")
    ptm.main(["seq", "-z", "1", "1"])
    assert capsys.readouterr().out == "10"


def test_seq_num_omitted_with_space_pad_uses_full_sequence_width(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MICRO_CURSOR_COUNT", "10")
    monkeypatch.setenv("MICRO_CURSOR_INDEX", "0")
    ptm.main(["seq", "-p", "1", "1"])
    assert capsys.readouterr().out == " 1"


def test_seq_explicit_num_takes_precedence_over_env(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MICRO_CURSOR_COUNT", "10")
    monkeypatch.setenv("MICRO_CURSOR_INDEX", "5")
    ptm.main(["seq", "0", "1", "3"])
    assert capsys.readouterr().out == "0 1 2"


def test_seq_num_omitted_missing_env_errors(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MICRO_CURSOR_COUNT", raising=False)
    monkeypatch.delenv("MICRO_CURSOR_INDEX", raising=False)
    with pytest.raises(SystemExit):
        ptm.main(["seq", "1", "1"])
    assert "MICRO_CURSOR_COUNT" in capsys.readouterr().err


def test_seq_num_omitted_partial_env_errors(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MICRO_CURSOR_COUNT", "5")
    monkeypatch.delenv("MICRO_CURSOR_INDEX", raising=False)
    with pytest.raises(SystemExit):
        ptm.main(["seq", "1", "1"])
    assert "MICRO_CURSOR_INDEX" in capsys.readouterr().err


def test_seq_num_omitted_non_integer_env_errors(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MICRO_CURSOR_COUNT", "abc")
    monkeypatch.setenv("MICRO_CURSOR_INDEX", "0")
    with pytest.raises(SystemExit):
        ptm.main(["seq", "1", "1"])
    assert "integer" in capsys.readouterr().err


def test_seq_num_omitted_index_out_of_range_errors(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Editor invariant violation: INDEX must be in [0, COUNT). Surface it
    # as a clean error rather than letting a stray ValueError leak out.
    monkeypatch.setenv("MICRO_CURSOR_COUNT", "3")
    monkeypatch.setenv("MICRO_CURSOR_INDEX", "5")
    with pytest.raises(SystemExit):
        ptm.main(["seq", "1", "1"])
    assert "out of range" in capsys.readouterr().err


def test_dec2hex(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "255\n4096\n0\n")
    ptm.main(["dec2hex"])
    assert capsys.readouterr().out == "ff\n1000\n0"


def test_dec2hex_positional(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["dec2hex", "255", "4096"])
    assert capsys.readouterr().out == "ff\n1000"


def test_bin2hex(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "1010\n11111111\n")
    ptm.main(["bin2hex"])
    assert capsys.readouterr().out == "a\nff"


def test_hex2bin(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "ff\n10\n")
    ptm.main(["hex2bin"])
    assert capsys.readouterr().out == "11111111\n10000"


def test_oct2dec(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "77\n10\n")
    ptm.main(["oct2dec"])
    assert capsys.readouterr().out == "63\n8"


def test_dec2bin(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "10\n255\n")
    ptm.main(["dec2bin"])
    assert capsys.readouterr().out == "1010\n11111111"


def test_all_pairwise_subcommands_registered() -> None:
    """The dispatch loop must register every src->dst pair exactly once."""
    parser = ptm.build_parser()
    subparsers_action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    names = set(subparsers_action.choices)
    expected = {f"{s}2{d}" for s in ptm._BASES for d in ptm._BASES if s != d}
    assert expected.issubset(names)
    assert len(expected) == 12


def test_every_subcommand_accepts_newline_flag() -> None:
    """`-n` / `--newline` / `--no-newline` is declared on a shared parent
    parser, so every subcommand must accept it without error."""
    parser = ptm.build_parser()
    subparsers_action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    for name, sp in subparsers_action.choices.items():
        option_strings = {opt for action in sp._actions for opt in action.option_strings}
        assert "-n" in option_strings, f"{name} missing -n"
        assert "--newline" in option_strings, f"{name} missing --newline"
        assert "--no-newline" in option_strings, f"{name} missing --no-newline"


def test_baseconv_bin_to_hex(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_stdin(monkeypatch, "1010\n11111111\n")
    ptm.main(["baseconv", "2", "16"])
    assert capsys.readouterr().out == "a\nff"


def test_baseconv_positional(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["baseconv", "2", "16", "1010", "11111111"])
    assert capsys.readouterr().out == "a\nff"


def test_baseconv_base64_alpha_positional(capsys: pytest.CaptureFixture[str]) -> None:
    # Alphabetic positional values must not be misread as options. "BA" in
    # RFC 4648 base 64 is one*64 + zero = 64.
    ptm.main(["baseconv", "64", "10", "BA"])
    assert capsys.readouterr().out == "64"


def test_baseconv_arbitrary_base(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_stdin(monkeypatch, "z\n10\n")
    ptm.main(["baseconv", "36", "10"])
    assert capsys.readouterr().out == "35\n36"


def test_baseconv_negative_passes_through(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_stdin(monkeypatch, "-ff\n")
    ptm.main(["baseconv", "16", "10"])
    assert capsys.readouterr().out == "-255"


def test_baseconv_dec_to_base64(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # RFC 4648 alphabet: 0->'A', 36->'k', 63->'/', 64->'BA' (one then zero).
    _set_stdin(monkeypatch, "0\n36\n63\n64\n4096\n")
    ptm.main(["baseconv", "10", "64"])
    assert capsys.readouterr().out == "A\nk\n/\nBA\nBAA"


def test_baseconv_base64_to_dec(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_stdin(monkeypatch, "A\nk\n/\nBA\nBAA\n")
    ptm.main(["baseconv", "64", "10"])
    assert capsys.readouterr().out == "0\n36\n63\n64\n4096"


def test_baseconv_base64_negative(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_stdin(monkeypatch, "-/\n")
    ptm.main(["baseconv", "64", "10"])
    assert capsys.readouterr().out == "-63"


def test_baseconv_base64_roundtrip(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # 16 -> base 64 -> base 16 should be the identity for any value.
    _set_stdin(monkeypatch, "deadbeef\n")
    ptm.main(["baseconv", "16", "64"])
    intermediate = capsys.readouterr().out.strip()
    _set_stdin(monkeypatch, intermediate + "\n")
    ptm.main(["baseconv", "64", "16"])
    assert capsys.readouterr().out == "deadbeef"


def test_baseconv_high_base_is_case_sensitive(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # In RFC 4648 base 64: 'a' = 26, 'A' = 0. These are distinct, unlike in base 16.
    _set_stdin(monkeypatch, "a\nA\n")
    ptm.main(["baseconv", "64", "10"])
    assert capsys.readouterr().out == "26\n0"


def test_baseconv_high_base_digits_are_not_positional(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Documents the trap: '1' = 53 and '0' = 52 in RFC 4648, so the literal
    # text "10" parsed at base 64 is 53*64 + 52 = 3444, not sixty-four.
    _set_stdin(monkeypatch, "10\n")
    ptm.main(["baseconv", "64", "10"])
    assert capsys.readouterr().out == "3444"


def test_baseconv_low_base_remains_case_insensitive(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The alphabet switch at base 37 must not regress base 16.
    _set_stdin(monkeypatch, "ff\nFF\n")
    ptm.main(["baseconv", "16", "10"])
    assert capsys.readouterr().out == "255\n255"


def test_baseconv_rejects_out_of_range_base(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        ptm.main(["baseconv", "1", "10"])
    assert "must be in 2..64" in capsys.readouterr().err

    with pytest.raises(SystemExit):
        ptm.main(["baseconv", "10", "65"])
    assert "must be in 2..64" in capsys.readouterr().err


def test_no_subcommand_errors() -> None:
    with pytest.raises(SystemExit):
        ptm.main([])


def test_unknown_subcommand_errors() -> None:
    with pytest.raises(SystemExit):
        ptm.main(["bogus"])


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        ptm.main(["--version"])
    assert exc.value.code == 0
    assert ptm.__version__ in capsys.readouterr().out
