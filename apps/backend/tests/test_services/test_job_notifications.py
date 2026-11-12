"""#494 AC2–AC5: who is told a job ended, what the message says, and what it never does.

Real Mongo throughout: the preference is a real document and the address comes from a real
row in the NextAuth `users` collection. Only the provider is replaced, at
`email_service.send`, so every assertion is on the message that would have gone out.
"""

import logging

import pytest
import pytest_asyncio
from bson import ObjectId

from app.models.notification_preference import NotificationPreference
from app.services import email_service, job_notifications

ADDRESS = "analyst@customer.example"


@pytest.fixture
def outbox(monkeypatch) -> list[dict[str, str]]:
    """A configured sender whose messages land in a list."""
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("EMAIL_FROM", "SheetPredict <jobs@mail.example>")
    sent: list[dict[str, str]] = []

    async def deliver(to: str, subject: str, text: str, *, idempotency_key: str) -> bool:
        sent.append({"to": to, "subject": subject, "text": text, "key": idempotency_key})
        return True

    monkeypatch.setattr(email_service, "send", deliver)
    return sent


@pytest_asyncio.fixture
async def account(setup_database):
    """A signed-up account as the NextAuth adapter stores it; yields its user id."""
    users = NotificationPreference.get_motor_collection().database["users"]
    user_id = ObjectId()
    await users.insert_one({"_id": user_id, "email": ADDRESS, "name": "An Analyst"})
    yield str(user_id)
    await users.delete_one({"_id": user_id})


class TestPreference:
    async def test_an_account_that_never_chose_gets_job_emails(self, setup_database):
        assert await job_notifications.wants_job_emails("someone") is True

    async def test_a_choice_is_stored_and_read_back(self, setup_database):
        await job_notifications.set_job_emails("someone", False)

        assert await job_notifications.wants_job_emails("someone") is False
        assert await job_notifications.wants_job_emails("someone-else") is True

    async def test_changing_a_choice_keeps_one_row(self, setup_database):
        await job_notifications.set_job_emails("someone", False)
        await job_notifications.set_job_emails("someone", True)

        rows = await NotificationPreference.find(NotificationPreference.user_id == "someone").to_list()
        assert [row.job_emails for row in rows] == [True]


class TestAFinishedJob:
    async def test_a_completed_job_mails_its_owner(self, account, outbox):
        await job_notifications.job_finished(account, 'Training "Churn"', job_id="m1", key="training-m1-completed")

        (message,) = outbox
        assert message["to"] == ADDRESS
        assert message["subject"] == 'Training "Churn" finished'
        assert 'Training "Churn" finished on SheetPredict.' in message["text"]
        assert message["key"] == "training-m1-completed"

    async def test_a_failed_job_mails_the_reason(self, account, outbox):
        await job_notifications.job_finished(
            account,
            "Your batch prediction",
            job_id="j1",
            failure_reason="The input file has no rows.",
            key="batch-j1-failed",
        )

        (message,) = outbox
        assert message["subject"] == "Your batch prediction failed"
        assert "Your batch prediction did not finish." in message["text"]
        assert "Reason: The input file has no rows." in message["text"]

    async def test_the_message_names_the_job_id_a_failure_reason_asks_for(self, account, outbox):
        # The generic reason reads "Quote this job's id to support".
        await job_notifications.job_finished(
            account, "Your training run", job_id="model_20261111_abc", failure_reason="Unexpected.", key="k1"
        )
        await job_notifications.job_finished(account, "Your training run", job_id="model_20261111_abc", key="k2")

        failed, finished = (message["text"] for message in outbox)
        assert "Job id: model_20261111_abc" in failed
        assert "Job id: model_20261111_abc" in finished

    async def test_the_message_links_the_app_and_says_how_to_stop(
        self, account, outbox, monkeypatch
    ):
        monkeypatch.setenv("PUBLIC_API_URL", "https://app.example/api/v1")

        await job_notifications.job_finished(account, "Your training run", job_id="job_1", key="k")

        text = outbox[0]["text"]
        assert "https://app.example\n" in text
        assert "https://app.example/settings" in text
        assert "/api/v1" not in text

    async def test_without_a_public_address_the_message_carries_no_link(
        self, account, outbox, monkeypatch
    ):
        monkeypatch.delenv("PUBLIC_API_URL", raising=False)

        await job_notifications.job_finished(account, "Your training run", job_id="job_1", key="k")

        text = outbox[0]["text"]
        assert "http" not in text
        assert "Settings" in text

    async def test_a_label_cannot_break_the_subject_line(self, account, outbox):
        await job_notifications.job_finished(account, 'Training "a\r\nBcc: x"', job_id="job_1", key="k")

        assert "\n" not in outbox[0]["subject"]
        assert "\r" not in outbox[0]["subject"]

    async def test_a_long_label_is_cut_to_the_stated_length(self, account, outbox):
        # #1204: a model name or filename is user-typed (a filename may be 255 characters).
        name = "quarterly churn " * 20
        await job_notifications.job_finished(account, f'Training "{name}"', job_id="job_1", key="k")

        label = 'Training "' + name[:109] + "…"
        assert len(label) == job_notifications.MAX_LABEL_LENGTH == 120
        assert outbox[0]["subject"] == f"{label} finished"
        assert outbox[0]["text"].startswith(f"{label} finished on SheetPredict.")
        assert name not in outbox[0]["text"]

    async def test_a_label_of_exactly_the_stated_length_is_kept_whole(self, account, outbox):
        label = "x" * job_notifications.MAX_LABEL_LENGTH
        await job_notifications.job_finished(
            account, label, job_id="job_1", failure_reason="Unexpected.", key="k"
        )

        assert outbox[0]["subject"] == f"{label} failed"
        assert outbox[0]["text"].startswith(f"{label} did not finish.")

    async def test_the_body_names_the_job_on_one_line_too(self, account, outbox):
        await job_notifications.job_finished(account, 'Training "a\r\nb"', job_id="job_1", key="k")

        assert outbox[0]["text"].startswith('Training "a b" finished on SheetPredict.')


class TestWhoIsNotMailed:
    async def test_an_account_that_opted_out(self, account, outbox):
        await job_notifications.set_job_emails(account, False)

        await job_notifications.job_finished(account, "Your training run", job_id="job_1", key="k")

        assert outbox == []

    async def test_a_user_id_with_no_account_row(self, setup_database, outbox):
        await job_notifications.job_finished(str(ObjectId()), "Your training run", job_id="job_1", key="k")
        await job_notifications.job_finished("dev-user-default", "Your training run", job_id="job_1", key="k")

        assert outbox == []

    async def test_an_account_without_an_address(self, setup_database, outbox):
        users = NotificationPreference.get_motor_collection().database["users"]
        user_id = ObjectId()
        await users.insert_one({"_id": user_id, "name": "No Address"})
        try:
            await job_notifications.job_finished(str(user_id), "Your training run", job_id="job_1", key="k")
        finally:
            await users.delete_one({"_id": user_id})

        assert outbox == []

    async def test_nobody_when_mail_is_not_configured(self, account, outbox, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "")

        await job_notifications.job_finished(account, "Your training run", job_id="job_1", key="k")

        assert outbox == []


class TestAFailureToNotify:
    async def test_a_provider_error_is_swallowed_and_logged_by_class(
        self, account, outbox, monkeypatch, caplog
    ):
        async def explode(*_args, **_kwargs):
            raise RuntimeError(f"smtp says no to {ADDRESS}")

        monkeypatch.setattr(email_service, "send", explode)

        with caplog.at_level(logging.WARNING, logger=job_notifications.logger.name):
            await job_notifications.job_finished(account, "Your training run", job_id="job_1", key="k")

        assert "RuntimeError" in caplog.text
        assert ADDRESS not in caplog.text

    async def test_a_database_error_is_swallowed(self, account, outbox, monkeypatch):
        async def unreachable(_user_id: str) -> bool:
            raise ConnectionError("mongo is away")

        monkeypatch.setattr(job_notifications, "wants_job_emails", unreachable)

        await job_notifications.job_finished(account, "Your training run", job_id="job_1", key="k")

        assert outbox == []
