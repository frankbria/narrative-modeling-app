"""One-click unsubscribe from job mail (#1206, RFC 8058).

Every job mail carries a link that turns that account's job mail off without signing in.
The link holds a token: the account id, when the mail was built, and an HMAC over both
under the artifact signing key (`app/utils/artifact_signing.py`, which any deploy has
through `NEXTAUTH_SECRET`), so nobody can make one for another account. A purpose prefix
keeps a signature over other bytes from passing as a link.

A link works until the account's choice changes after the mail was built: someone holding
an old mail cannot keep switching off mail the owner turned back on. Nothing is stored per
link.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from pymongo.errors import DuplicateKeyError

from app.models.notification_preference import NotificationPreference
from app.utils.artifact_signing import sign_bytes, verify_bytes
from app.utils.datetime import utcnow

_PURPOSE = "job-mail-unsubscribe"
_TOKEN = re.compile(r"([A-Za-z0-9_-]+)\.([0-9]{1,15})\.([0-9a-f]{64})", re.ASCII)


@dataclass(frozen=True)
class UnsubscribeLink:
    user_id: str
    issued_at: datetime


def _signed_words(user_id: str, issued_ms: int) -> bytes:
    return f"{_PURPOSE}:{user_id}:{issued_ms}".encode()


def token_for(user_id: str, issued_at: datetime) -> str:
    """The token for a mail to `user_id` built at `issued_at` (kept to the millisecond,
    MongoDB's precision, so it compares exactly with the stored `updated_at`). Mail goes
    only to accounts whose id is an ObjectId, which the token carries as it is."""
    issued_ms = int(issued_at.timestamp() * 1000)
    return f"{user_id}.{issued_ms}.{sign_bytes(_signed_words(user_id, issued_ms))}"


def read(token: str) -> UnsubscribeLink | None:
    """The link `token` stands for, or None when it is malformed or not ours."""
    match = _TOKEN.fullmatch(token)
    if match is None:
        return None
    user_id, issued, signature = match.groups()
    if not verify_bytes(_signed_words(user_id, int(issued)), signature):
        return None
    return UnsubscribeLink(user_id, datetime.fromtimestamp(int(issued) / 1000, UTC))


async def turn_off(user_id: str, issued_at: datetime) -> bool:
    """Turn the account's job mail off unless its choice changed at or after `issued_at`.
    True when its job mail is off afterwards: a refused link whose account is already off
    reads as done."""
    try:
        # One write: the filter matches only a choice made before the link was built, so
        # a later choice leaves the row unmatched and the upsert hits the unique index.
        # Strictly before: a choice stored in the link's own millisecond may be the later.
        await NotificationPreference.get_motor_collection().update_one(
            {"user_id": user_id, "updated_at": {"$lt": issued_at}},
            {"$set": {"user_id": user_id, "job_emails": False, "updated_at": utcnow()}},
            upsert=True,
        )
    except DuplicateKeyError:
        current = await NotificationPreference.find_one(
            NotificationPreference.user_id == user_id
        )
        return current is not None and not current.job_emails
    return True
