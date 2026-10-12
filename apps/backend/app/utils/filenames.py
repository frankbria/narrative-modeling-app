"""Client-supplied filenames, made safe to store (#585).

The S3 key never depends on the filename (#464), but ``UserData.filename`` /
``original_filename`` used to be stored verbatim — a trap for the next consumer
that builds a ``Content-Disposition`` header (CR/LF injection) or a filesystem
path (traversal) from them. Normalise once, at ingestion, and store only that.
"""

import re
import unicodedata
from typing import Annotated, Any

from pydantic import AfterValidator

MAX_FILENAME_LENGTH = 255
#: Longest input we bother scanning: real filenames are a few hundred bytes; a
#: multipart filename of megabytes is not one, and the O(n) Unicode pass below
#: should not be the attacker's lever.
_SCAN_LIMIT = 4096
_FALLBACK = "upload"
# C0 controls, DEL, and the double quote — the character that ends a quoted
# Content-Disposition parameter. Unicode Cc/Cf (zero-width, bidi overrides such
# as the RTLO extension-spoof) go in the category pass below.
_STRIP = re.compile(r'[\x00-\x1f\x7f"]')
_EDGE_DOTS_AND_SPACE = re.compile(r"^[.\s]+|[.\s]+$")


def sanitize_filename(name: str, max_length: int = MAX_FILENAME_LENGTH) -> str:
    """Return a display-safe basename: no path segments, no control characters
    or quotes, no leading/trailing dots or whitespace, never empty, at most
    ``max_length`` characters with the extension preserved. Idempotent. Odd-but-
    honest names (spaces, parentheses, accents, dashes) survive unchanged.
    """
    # Basename after either separator; a trailing separator yields "".
    base = name.replace("\\", "/").rsplit("/", 1)[-1][:_SCAN_LIMIT]
    base = _STRIP.sub("", base)
    base = "".join(ch for ch in base if unicodedata.category(ch) not in ("Cc", "Cf"))
    # One regex, both edges: alternating dots and spaces (" . .x") fall together,
    # and a trailing dot/space (Windows-hostile, and what truncation could leave)
    # goes too.
    base = _EDGE_DOTS_AND_SPACE.sub("", base)
    if not base:
        return _FALLBACK
    if len(base) > max_length:
        stem, dot, ext = base.rpartition(".")
        keep = max_length - len(ext) - 1  # room left for the stem
        if dot and stem and 0 < len(ext) <= 16 and keep > 0:
            base = stem[:keep] + "." + ext
        else:
            base = base[:max_length]
        base = _EDGE_DOTS_AND_SPACE.sub("", base) or _FALLBACK
    return base


#: Field type for a client-supplied filename: validated once, shared by every
#: document that stores one (#585), so the two models cannot drift apart.
SafeFilename = Annotated[str, AfterValidator(sanitize_filename)]


def excel_file_type(*names: str | None) -> str:
    """``"xls"`` or ``"xlsx"``: the first of ``names`` (a filename, an object URL) whose
    extension says which. A workbook nothing names is the current format."""
    for name in names:
        extension = (name or "").split("?", 1)[0].rsplit(".", 1)[-1].lower()
        if extension in ("xls", "xlsx"):
            return extension
    return "xlsx"


def excel_under_its_extension(document: Any) -> Any:
    """Store an Excel dataset's ``file_type`` as its extension, never ``"excel"`` (#902).

    The body of a ``model_validator(mode="before")`` on both dataset documents. Three
    upload routes wrote ``"excel"`` and two wrote ``"xls"``/``"xlsx"``, and readers
    disagreed about which they knew, so a workbook uploaded through the UI failed at
    whichever stage met a reader that knew only the extensions. One spelling, set where
    every writer passes; and because validators also run when a row is read, a row
    stored before this reads back under its extension, so no reader needs the old one.
    """
    if not isinstance(document, dict) or str(document.get("file_type") or "").lower() != "excel":
        return document
    names = (document.get(key) for key in ("original_filename", "filename", "s3_url", "file_path"))
    return {**document, "file_type": excel_file_type(*names)}

