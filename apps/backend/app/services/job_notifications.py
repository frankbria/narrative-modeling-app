"""Mail an account when one of its background jobs ends (#494).

Every place a job reaches COMPLETED or FAILED calls in here: `job_finished` for a training
run, `batch_job_finished` for a batch job, from the job's own task and from the stale-job
reaper. Neither function raises, so a notification cannot change the outcome it reports.

A message carries the job's label and id, the stored user-safe failure reason
(`app/utils/job_failures.py`), the app's address and how to stop the mails. Nothing else:
no dataset contents, no storage locations, no tokens.
"""

import logging
from collections.abc import Coroutine

from bson import ObjectId

from app.config import public_api_url
from app.models.batch_job import BatchJob, JobStatus
from app.models.notification_preference import NotificationPreference
from app.services import email_service
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)

_API_PATH = "/api/v1"
_REPORTED = (JobStatus.COMPLETED, JobStatus.FAILED)
_NO_REASON = "No reason was recorded."


async def wants_job_emails(user_id: str) -> bool:
    """The account's choice; an account that never chose is mailed."""
    preference = await NotificationPreference.find_one(NotificationPreference.user_id == user_id)
    return preference.job_emails if preference else True


async def set_job_emails(user_id: str, enabled: bool) -> None:
    # One upsert, so two first saves meet on the unique `user_id` index.
    await NotificationPreference.get_motor_collection().update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "job_emails": enabled, "updated_at": utcnow()}},
        upsert=True,
    )


async def _address_of(user_id: str) -> str | None:
    """The address the account signed up with, from the NextAuth adapter's `users`
    collection (same database, #545). None for an id with no row there: the development
    and test identities are not ObjectIds and have no account."""
    if not ObjectId.is_valid(user_id):
        return None
    users = NotificationPreference.get_motor_collection().database["users"]
    account = await users.find_one({"_id": ObjectId(user_id)}, {"email": 1})
    return (account or {}).get("email") or None


def _app_url() -> str | None:
    # shortcut: assumes the app is served from the API's own origin, true of every
    # deployment today; give the app its own setting when the two are split.
    api = public_api_url()
    return api.removesuffix(_API_PATH) if api else None


def _message(job: str, job_id: str, failure_reason: str | None) -> tuple[str, str]:
    """Subject and body. `job` is caller-built and may quote a name the user typed, so
    the subject keeps it to one line."""
    outcome = "failed" if failure_reason else "finished"
    subject = " ".join(f"{job} {outcome}".split())
    opening = (
        f"{job} did not finish.\n\nReason: {failure_reason}"
        if failure_reason
        else f"{job} finished on SheetPredict."
    )
    app_url = _app_url()
    link = f"\n\n{app_url}\n" if app_url else "\n"
    settings_page = f"Settings ({app_url}/settings)" if app_url else "Settings"
    footer = (
        "You are getting this because job emails are on for your SheetPredict account. "
        f"Turn them off under {settings_page}."
    )
    # The id is what support asks for, and what the generic failure reason tells the
    # reader to quote.
    return subject, f"{opening}\n\nJob id: {job_id}{link}\n{footer}\n"


async def _notify(
    user_id: str, job: str, job_id: str, failure_reason: str | None, key: str
) -> None:
    if not email_service.is_configured() or not await wants_job_emails(user_id):
        return
    address = await _address_of(user_id)
    if address is None:
        return
    subject, text = _message(job, job_id, failure_reason)
    await email_service.send(address, subject, text, idempotency_key=key)


async def _notify_batch(job_id: str) -> None:
    """Report what is stored, not what the run believes: its last write is conditional,
    and a cancel, the reaper or an erasure may have had the last word."""
    job = await BatchJob.find_one(BatchJob.job_id == job_id)
    if job is None or job.status not in _REPORTED:
        return
    await _notify(
        job.user_id,
        f"Your batch prediction of {job.progress.total_records:,} records",
        job_id,
        # The stored status decides the outcome: a failed job whose reason is missing
        # must not read as finished.
        (job.error_message or _NO_REASON) if job.status == JobStatus.FAILED else None,
        # Keyed on when this ending was stored: the run and the reaper reporting one
        # ending agree on it, and a retry's ending is a later one, mailed again.
        f"batch-{job_id}-{job.status.value}-{job.completed_at}",
    )


async def _quietly(notification: Coroutine[None, None, None]) -> None:
    try:
        await notification
    except Exception as exc:  # noqa: BLE001 - a notification must never fail its job
        logger.warning("Job notification not sent: %s", type(exc).__name__)


async def job_finished(
    user_id: str, job: str, *, job_id: str, failure_reason: str | None = None, key: str
) -> None:
    """Tell the owner that `job` (e.g. ``Training "Churn"``) ended: failed when a reason
    is given, finished otherwise. `key` identifies this ending: the provider delivers one
    message per key, the first, so a task and the reaper both reporting one failure mail
    the owner once."""
    await _quietly(_notify(user_id, job, job_id, failure_reason, key))


async def batch_job_finished(job_id: str) -> None:
    """Tell the owner of a batch job how it ended, if it is stored as COMPLETED or FAILED."""
    await _quietly(_notify_batch(job_id))


def training_failure_key(model_id: str) -> str:
    """One key for a training run's failure, shared by the task and the reaper."""
    return f"training-{model_id}-failed"
