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


class TestAttachmentDisposition:
    """#648: one builder for every download header, so a name cannot break out of it."""

    @staticmethod
    def _parsed(value: str) -> tuple[str, str]:
        """(the quoted fallback, the decoded filename*) of a Content-Disposition value."""
        import re
        from urllib.parse import unquote

        match = re.fullmatch(r'attachment; filename="([^"\\\r\n]*)"; filename\*=UTF-8\'\'([A-Za-z0-9%._~-]*)', value)
        assert match, value
        return match.group(1), unquote(match.group(2))

    def test_a_plain_name_is_quoted_and_repeated_encoded(self):
        from app.utils.filenames import attachment_disposition

        value = attachment_disposition("churn_1.0.onnx")

        assert value == "attachment; filename=\"churn_1.0.onnx\"; filename*=UTF-8''churn_1.0.onnx"

    def test_a_name_cannot_add_a_parameter_or_a_header(self):
        from app.utils.filenames import attachment_disposition

        value = attachment_disposition('churn"; x=y\r\nX-Injected: 1_1.0_inference.py')

        fallback, decoded = self._parsed(value)
        assert "\r" not in value and "\n" not in value
        assert fallback == decoded == "churn; x=yX-Injected: 1_1.0_inference.py"

    def test_a_name_outside_ascii_survives_in_the_encoded_form(self):
        from app.utils.filenames import attachment_disposition

        value = attachment_disposition("модель 客户_1.0.pmml")

        value.encode("latin-1")  # what the server does with a header
        fallback, decoded = self._parsed(value)
        assert decoded == "модель 客户_1.0.pmml"
        assert fallback.endswith("_1.0.pmml") and fallback.isascii()

    def test_a_path_is_reduced_to_its_last_segment(self):
        from app.utils.filenames import attachment_disposition

        assert self._parsed(attachment_disposition("..\\..\\etc/passwd_1.0.onnx"))[1] == "passwd_1.0.onnx"


def test_no_download_header_is_built_by_hand():
    """#648: eight routes interpolated a model's name into the header themselves. A
    new download goes through `attachment_disposition`, or it reopens the hole."""
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[2] / "app"
    by_hand = [
        str(path.relative_to(app_dir))
        for path in app_dir.rglob("*.py")
        if "attachment; filename" in path.read_text() and path.name != "filenames.py"
    ]

    assert by_hand == []
