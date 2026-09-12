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
