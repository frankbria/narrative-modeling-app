"""#1206: a job mail's unsubscribe link works without signing in, for its account only.

`GET` is the page the link in the message opens: it changes nothing, because mail
scanners open links. `POST` is RFC 8058's one-click request that mailbox providers send
(`List-Unsubscribe-Post: List-Unsubscribe=One-Click`), and what the page's button sends.
"""

from datetime import timedelta

from app.services import job_mail_unsubscribe
from app.services.job_notifications import set_job_emails, wants_job_emails
from app.utils.datetime import utcnow

URL = "/api/v1/users/unsubscribe/job-emails"
ONE_CLICK = {"List-Unsubscribe": "One-Click"}


def _token(user_id: str = "acct-1", minutes_ago: int = 0) -> str:
    return job_mail_unsubscribe.token_for(
        user_id, utcnow() - timedelta(minutes=minutes_ago)
    )


async def test_the_page_offers_the_button_and_changes_nothing(
    async_authorized_client, setup_database
):
    token = _token()

    response = await async_authorized_client.get(URL, params={"token": token})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<form method="post"' in response.text
    assert f'action="?token={token}"' in response.text
    assert await wants_job_emails("acct-1") is True


async def test_the_one_click_request_turns_that_accounts_mail_off(
    async_authorized_client, setup_database
):
    response = await async_authorized_client.post(
        URL, params={"token": _token()}, data=ONE_CLICK
    )

    assert response.status_code == 200
    assert "Job emails are off" in response.text
    assert await wants_job_emails("acct-1") is False
    assert await wants_job_emails("test_user_123") is True


async def test_a_forged_token_is_refused_and_changes_nothing(
    async_authorized_client, setup_database
):
    owner, issued, signature = _token().split(".")
    forged = f"{owner}.{issued}.{'0' * len(signature)}"

    page = await async_authorized_client.get(URL, params={"token": forged})
    click = await async_authorized_client.post(
        URL, params={"token": forged}, data=ONE_CLICK
    )

    assert (page.status_code, click.status_code) == (400, 400)
    assert "<form" not in page.text
    assert forged not in page.text
    assert await wants_job_emails("acct-1") is True


async def test_a_reused_link_cannot_turn_mail_off_after_it_was_turned_back_on(
    async_authorized_client, setup_database
):
    token = _token(minutes_ago=5)
    first = await async_authorized_client.post(
        URL, params={"token": token}, data=ONE_CLICK
    )
    await set_job_emails("acct-1", True)

    reused = await async_authorized_client.post(
        URL, params={"token": token}, data=ONE_CLICK
    )

    assert first.status_code == 200
    assert reused.status_code == 410
    assert "Settings" in reused.text
    assert await wants_job_emails("acct-1") is True


async def test_a_second_click_on_the_same_link_still_reads_as_off(
    async_authorized_client, setup_database
):
    token = _token()
    await async_authorized_client.post(URL, params={"token": token}, data=ONE_CLICK)

    again = await async_authorized_client.post(
        URL, params={"token": token}, data=ONE_CLICK
    )

    assert again.status_code == 200
    assert await wants_job_emails("acct-1") is False


async def test_a_request_without_a_token_is_refused(
    async_authorized_client, setup_database
):
    response = await async_authorized_client.post(URL, data=ONE_CLICK)

    assert response.status_code == 422
