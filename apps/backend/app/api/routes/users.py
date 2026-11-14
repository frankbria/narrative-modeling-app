"""Account-scoped settings of the signed-in user (#494), and the unsubscribe link a job
mail carries, which works without signing in (#1206)."""

import html

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from app.auth.nextauth_auth import get_current_user_id
from app.services import job_mail_unsubscribe, job_notifications

router = APIRouter()


class NotificationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_emails: bool = Field(
        description="Email the account when a training or batch prediction job ends"
    )


@router.get("/me/notification-preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user_id: str = Depends(get_current_user_id),
) -> NotificationPreferences:
    """Whether the caller is emailed when a job ends. On until turned off."""
    return NotificationPreferences(
        job_emails=await job_notifications.wants_job_emails(current_user_id)
    )


@router.put("/me/notification-preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user_id: str = Depends(get_current_user_id),
) -> NotificationPreferences:
    """Turn the caller's job emails on or off."""
    await job_notifications.set_job_emails(current_user_id, preferences.job_emails)
    return preferences


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SheetPredict job emails</title></head>
<body style="font-family: sans-serif; max-width: 32rem; margin: 3rem auto; padding: 0 1rem">
{body}
</body></html>
"""
_SIGN_IN_INSTEAD = "Sign in to SheetPredict and change job emails under Settings."
_NOT_VALID = f"<p>This unsubscribe link is not valid.</p><p>{_SIGN_IN_INSTEAD}</p>"
_OUT_OF_DATE = (
    "<p>This link is from an email sent before your job email setting last changed, so it "
    f"no longer works.</p><p>{_SIGN_IN_INSTEAD}</p>"
)
_DONE = "<p>Job emails are off for your account.</p><p>You can turn them back on under Settings.</p>"


def _page(body: str, status_code: int = 200) -> HTMLResponse:
    # A new response per request: middleware writes headers onto it.
    return HTMLResponse(
        _PAGE.format(body=body),
        status_code=status_code,
        # The address holds the token: keep it out of caches and of any referrer.
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


def _confirmation(token: str) -> HTMLResponse:
    action = html.escape(f"?token={token}")
    return _page(
        "<p>Stop the emails SheetPredict sends when a training or batch prediction job of "
        "your account ends?</p>"
        f'<form method="post" action="{action}">'
        '<button type="submit">Turn off job emails</button></form>'
    )


@router.get(
    job_notifications.UNSUBSCRIBE_PATH.removeprefix("/users"),
    response_class=HTMLResponse,
    responses={400: {"description": "The token is malformed or not ours"}},
)
async def job_emails_unsubscribe_page(token: str) -> HTMLResponse:
    """The page a job mail's unsubscribe link opens: one button that sends the POST.
    It changes nothing, because mail scanners open links."""
    if job_mail_unsubscribe.read(token) is None:
        return _page(_NOT_VALID, status_code=400)
    return _confirmation(token)


@router.post(
    job_notifications.UNSUBSCRIBE_PATH.removeprefix("/users"),
    response_class=HTMLResponse,
    responses={
        400: {"description": "The token is malformed or not ours"},
        410: {"description": "The account's choice changed after the mail was sent"},
    },
)
async def unsubscribe_from_job_emails(token: str) -> HTMLResponse:
    """Turn off job mail for the account the token names (RFC 8058 one-click; the
    `List-Unsubscribe=One-Click` body is accepted and not needed)."""
    link = job_mail_unsubscribe.read(token)
    if link is None:
        return _page(_NOT_VALID, status_code=400)
    if not await job_mail_unsubscribe.turn_off(link.user_id, link.issued_at):
        return _page(_OUT_OF_DATE, status_code=410)
    return _page(_DONE)
