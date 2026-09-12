"""Client-supplied filenames, made safe to store (#585).

The S3 key never depends on the filename (#464), but ``UserData.filename`` /
``original_filename`` used to be stored verbatim — a trap for the next consumer
that builds a ``Content-Disposition`` header (CR/LF injection) or a filesystem
path (traversal) from them. Normalise once, at ingestion, and store only that.
"""

import re
import unicodedata

MAX_FILENAME_LENGTH = 255
_FALLBACK = "upload"
# Controls (C0 + DEL) and the Unicode category Cc/Cf: CR, LF, NUL, tabs, zero-width joiners…
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_filename(name: str, max_length: int = MAX_FILENAME_LENGTH) -> str:
    """Return a display-safe basename: no path segments, no control characters,
    no leading dots, never empty, at most ``max_length`` characters with the
    extension preserved. Idempotent. Odd-but-honest names survive unchanged.
    """
    # Basename after either separator; a trailing separator yields "".
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    base = _CONTROL.sub("", base)
    base = "".join(ch for ch in base if unicodedata.category(ch) not in ("Cc", "Cf"))
    base = base.strip().lstrip(".").strip()
    if not base:
        return _FALLBACK
    if len(base) > max_length:
        stem, dot, ext = base.rpartition(".")
        if dot and stem and len(ext) <= 16:
            base = stem[: max_length - len(ext) - 1] + "." + ext
        else:
            base = base[:max_length]
    return base
