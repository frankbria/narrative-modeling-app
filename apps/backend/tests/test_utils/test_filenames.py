"""sanitize_filename (#585): what a client-supplied name becomes before it is stored."""

import pytest

from app.utils.filenames import sanitize_filename


@pytest.mark.parametrize("raw,expected", [
    ("report.csv", "report.csv"),
    ("Q3 sales (final).xlsx", "Q3 sales (final).xlsx"),  # odd-but-honest names survive
    ("../../etc/passwd.csv", "passwd.csv"),
    ("..\\..\\windows\\system32\\hosts.csv", "hosts.csv"),
    ("a\r\nContent-Type: text-html\r\n.csv", "aContent-Type: text-html.csv"),  # CR/LF gone, header text inert
    ("a\r\nContent-Type: text/html\r\n.csv", "html.csv"),  # the slash is a separator: basename wins
    ("nul\x00byte.csv", "nulbyte.csv"),
    (".hidden.csv", "hidden.csv"),
    ("   spaced.csv  ", "spaced.csv"),
    ("..", "upload"),
    ("/", "upload"),
    ("", "upload"),
    (" . .foo.csv", "foo.csv"),  # alternating dots and spaces at the edge
    ("name.csv.", "name.csv"),  # trailing dot goes too
    ('evil".csv', "evil.csv"),  # the quote that ends a Content-Disposition parameter
    ("\u202egnp.csv", "gnp.csv"),  # RTLO extension spoof is a Cf character
])
def test_table(raw, expected):
    assert sanitize_filename(raw) == expected


def test_length_is_capped_and_the_extension_survives():
    out = sanitize_filename("x" * 300 + ".parquet")
    assert len(out) == 255
    assert out.endswith(".parquet")


def test_idempotent():
    for raw in ("../../etc/passwd.csv", "a\r\nb.csv", "x" * 300 + ".csv"):
        once = sanitize_filename(raw)
        assert sanitize_filename(once) == once


def test_a_huge_input_is_bounded_before_the_unicode_pass():
    # A multi-megabyte "filename" is not one: it is cut at the scan bound first,
    # so even its extension is not guaranteed — only the size is.
    assert len(sanitize_filename("a" * 5_000_000 + ".csv")) == 255
    # A merely long name keeps its extension.
    assert sanitize_filename("a" * 3000 + ".csv").endswith(".csv")


def test_truncation_never_leaves_a_trailing_dot():
    out = sanitize_filename("x" * 254 + "." + "y" * 40)  # 40-char "extension" is not one
    assert not out.endswith(".") and len(out) <= 255


def test_a_small_max_length_never_slices_from_the_end():
    # keep = max_length - len(ext) - 1 would be negative here; that must not turn
    # into a Python slice-from-the-end.
    out = sanitize_filename("abcdefghij.parquet", max_length=6)
    assert out == "abcdef"
