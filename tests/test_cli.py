"""End-to-end CLI tests for ptm.

These exercise `ptm.main(argv)` with monkeypatched stdin and assert on captured
stdout. Per-function unit tests are covered by the doctests in `ptm.py` and
collected by pytest via `--doctest-modules`.
"""

import argparse
import io

import pytest

import ptm


def _set_stdin(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def test_inc(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "1\n2\n10\n")
    ptm.main(["inc", "1"])
    assert capsys.readouterr().out == "2\n3\n11\n"


def test_inc_negative(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "100\n0\n")
    ptm.main(["inc", "-5"])
    assert capsys.readouterr().out == "95\n-5\n"


def test_inc_skips_blank_lines(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_stdin(monkeypatch, "1\n\n  \n2\n")
    ptm.main(["inc", "10"])
    assert capsys.readouterr().out == "11\n12\n"


def test_dec(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "10\n5\n1\n")
    ptm.main(["dec", "1"])
    assert capsys.readouterr().out == "9\n4\n0\n"


def test_dec_negative(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "10\n0\n")
    ptm.main(["dec", "-5"])
    assert capsys.readouterr().out == "15\n5\n"


def test_eval(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "1+2\n2**10\n")
    ptm.main(["eval"])
    assert capsys.readouterr().out == "3\n1024\n"


def test_seq_ascending(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "0", "2", "3"])
    assert capsys.readouterr().out == "0 2 4\n"


def test_seq_descending(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "10", "-2", "4"])
    assert capsys.readouterr().out == "10 8 6 4\n"


def test_seq_zero_increment_repeats(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "7", "0", "3"])
    assert capsys.readouterr().out == "7 7 7\n"


def test_seq_single_element_has_no_separator(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "42", "1", "1"])
    assert capsys.readouterr().out == "42\n"


def test_seq_zero_count_is_empty(capsys: pytest.CaptureFixture[str]) -> None:
    # Empty sequence must produce zero bytes of output (not even a trailing
    # newline), so a `read` from a script can distinguish "empty" from "blank line".
    ptm.main(["seq", "0", "1", "0"])
    assert capsys.readouterr().out == ""


def test_seq_negative_count_is_empty(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "0", "1", "-3"])
    assert capsys.readouterr().out == ""


def test_seq_zero_pad(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "-z", "8", "1", "3"])
    assert capsys.readouterr().out == "08 09 10\n"


def test_seq_space_pad(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "-p", "8", "1", "3"])
    assert capsys.readouterr().out == " 8  9 10\n"


def test_seq_zero_pad_with_negatives_is_sign_aware(capsys: pytest.CaptureFixture[str]) -> None:
    # `-1` is two chars; zero-padded `0` and `1` must become `00`/`01`, not
    # something silly like `0-1`. Matches `str.zfill` / `f"{n:03d}"`.
    ptm.main(["seq", "-z", "-1", "1", "3"])
    assert capsys.readouterr().out == "-1 00 01\n"


def test_seq_space_pad_with_negatives(capsys: pytest.CaptureFixture[str]) -> None:
    ptm.main(["seq", "-p", "-1", "1", "3"])
    assert capsys.readouterr().out == "-1  0  1\n"


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
    assert capsys.readouterr().out == "1\n"

    monkeypatch.setenv("MICRO_CURSOR_INDEX", "4")
    ptm.main(["seq", "1", "1"])
    assert capsys.readouterr().out == "5\n"


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
    assert capsys.readouterr().out == "01\n"

    monkeypatch.setenv("MICRO_CURSOR_INDEX", "9")
    ptm.main(["seq", "-z", "1", "1"])
    assert capsys.readouterr().out == "10\n"


def test_seq_num_omitted_with_space_pad_uses_full_sequence_width(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MICRO_CURSOR_COUNT", "10")
    monkeypatch.setenv("MICRO_CURSOR_INDEX", "0")
    ptm.main(["seq", "-p", "1", "1"])
    assert capsys.readouterr().out == " 1\n"


def test_seq_explicit_num_takes_precedence_over_env(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MICRO_CURSOR_COUNT", "10")
    monkeypatch.setenv("MICRO_CURSOR_INDEX", "5")
    ptm.main(["seq", "0", "1", "3"])
    assert capsys.readouterr().out == "0 1 2\n"


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
    assert capsys.readouterr().out == "ff\n1000\n0\n"


def test_bin2hex(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "1010\n11111111\n")
    ptm.main(["bin2hex"])
    assert capsys.readouterr().out == "a\nff\n"


def test_hex2bin(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "ff\n10\n")
    ptm.main(["hex2bin"])
    assert capsys.readouterr().out == "11111111\n10000\n"


def test_oct2dec(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "77\n10\n")
    ptm.main(["oct2dec"])
    assert capsys.readouterr().out == "63\n8\n"


def test_dec2bin(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch, "10\n255\n")
    ptm.main(["dec2bin"])
    assert capsys.readouterr().out == "1010\n11111111\n"


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


def test_baseconv_bin_to_hex(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_stdin(monkeypatch, "1010\n11111111\n")
    ptm.main(["baseconv", "2", "16"])
    assert capsys.readouterr().out == "a\nff\n"


def test_baseconv_arbitrary_base(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_stdin(monkeypatch, "z\n10\n")
    ptm.main(["baseconv", "36", "10"])
    assert capsys.readouterr().out == "35\n36\n"


def test_baseconv_negative_passes_through(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_stdin(monkeypatch, "-ff\n")
    ptm.main(["baseconv", "16", "10"])
    assert capsys.readouterr().out == "-255\n"


def test_baseconv_dec_to_base64(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # RFC 4648 alphabet: 0->'A', 36->'k', 63->'/', 64->'BA' (one then zero).
    _set_stdin(monkeypatch, "0\n36\n63\n64\n4096\n")
    ptm.main(["baseconv", "10", "64"])
    assert capsys.readouterr().out == "A\nk\n/\nBA\nBAA\n"


def test_baseconv_base64_to_dec(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_stdin(monkeypatch, "A\nk\n/\nBA\nBAA\n")
    ptm.main(["baseconv", "64", "10"])
    assert capsys.readouterr().out == "0\n36\n63\n64\n4096\n"


def test_baseconv_base64_negative(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_stdin(monkeypatch, "-/\n")
    ptm.main(["baseconv", "64", "10"])
    assert capsys.readouterr().out == "-63\n"


def test_baseconv_base64_roundtrip(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # 16 -> base 64 -> base 16 should be the identity for any value.
    _set_stdin(monkeypatch, "deadbeef\n")
    ptm.main(["baseconv", "16", "64"])
    intermediate = capsys.readouterr().out.strip()
    _set_stdin(monkeypatch, intermediate + "\n")
    ptm.main(["baseconv", "64", "16"])
    assert capsys.readouterr().out == "deadbeef\n"


def test_baseconv_high_base_is_case_sensitive(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # In RFC 4648 base 64: 'a' = 26, 'A' = 0. These are distinct, unlike in base 16.
    _set_stdin(monkeypatch, "a\nA\n")
    ptm.main(["baseconv", "64", "10"])
    assert capsys.readouterr().out == "26\n0\n"


def test_baseconv_high_base_digits_are_not_positional(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Documents the trap: '1' = 53 and '0' = 52 in RFC 4648, so the literal
    # text "10" parsed at base 64 is 53*64 + 52 = 3444, not sixty-four.
    _set_stdin(monkeypatch, "10\n")
    ptm.main(["baseconv", "64", "10"])
    assert capsys.readouterr().out == "3444\n"


def test_baseconv_low_base_remains_case_insensitive(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The alphabet switch at base 37 must not regress base 16.
    _set_stdin(monkeypatch, "ff\nFF\n")
    ptm.main(["baseconv", "16", "10"])
    assert capsys.readouterr().out == "255\n255\n"


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
