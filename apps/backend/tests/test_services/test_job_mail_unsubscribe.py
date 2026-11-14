"""#1206: the token a job mail's unsubscribe link carries, and what using it does.

Real Mongo: the preference is a real `NotificationPreference` row.
"""

from datetime import timedelta

from app.models.notification_preference import NotificationPreference
from app.services import job_mail_unsubscribe
from app.services.job_notifications import set_job_emails, wants_job_emails
from app.utils.datetime import as_utc, utcnow


def _forge(token: str, **parts: str) -> str:
    owner, issued, signature = token.split(".")
    replaced = {"owner": owner, "issued": issued, "signature": signature} | parts
    return f"{replaced['owner']}.{replaced['issued']}.{replaced['signature']}"


class TestTheToken:
    def test_a_token_reads_back_as_its_account_and_issue_time(self):
        issued_at = utcnow()

        link = job_mail_unsubscribe.read(
            job_mail_unsubscribe.token_for("acct-1", issued_at)
        )

        assert link is not None
        assert link.user_id == "acct-1"
        assert abs(link.issued_at - issued_at) < timedelta(milliseconds=1)

    def test_a_token_names_another_account_only_with_its_own_signature(self):
        mine = job_mail_unsubscribe.token_for("acct-1", utcnow())
        theirs = job_mail_unsubscribe.token_for("acct-2", utcnow())

        swapped = _forge(mine, owner=theirs.split(".")[0])

        assert job_mail_unsubscribe.read(swapped) is None

    def test_a_token_with_a_changed_issue_time_is_refused(self):
        token = job_mail_unsubscribe.token_for("acct-1", utcnow())

        assert job_mail_unsubscribe.read(_forge(token, issued=str(10**13))) is None

    def test_a_token_signed_with_another_secret_is_refused(self, monkeypatch):
        monkeypatch.delenv("ARTIFACT_SIGNING_KEY", raising=False)
        monkeypatch.setenv("NEXTAUTH_SECRET", "one-secret")
        token = job_mail_unsubscribe.token_for("acct-1", utcnow())

        monkeypatch.setenv("NEXTAUTH_SECRET", "another-secret")

        assert job_mail_unsubscribe.read(token) is None

    def test_the_signature_is_not_an_artifact_signature_of_the_same_words(self):
        """The key is shared with artifact signing (#266); the purpose prefix keeps a
        signature over other bytes from passing as a link."""
        from app.utils.artifact_signing import sign_bytes

        token = job_mail_unsubscribe.token_for("acct-1", utcnow())
        owner, issued, _ = token.split(".")

        bare = sign_bytes(f"acct-1:{issued}".encode())

        assert job_mail_unsubscribe.read(f"{owner}.{issued}.{bare}") is None

    def test_malformed_tokens_are_refused(self):
        for token in (
            "",
            "abc",
            "a.b.c",
            "acct.12.zz",
            "acct.١٢." + "0" * 64,
            "a/b.1." + "0" * 64,
        ):
            assert job_mail_unsubscribe.read(token) is None, token


class TestTurningMailOff:
    async def test_a_link_turns_off_an_account_that_never_chose(self, setup_database):
        assert await job_mail_unsubscribe.turn_off("acct-1", utcnow()) is True

        assert await wants_job_emails("acct-1") is False

    async def test_it_turns_off_that_account_only(self, setup_database):
        await job_mail_unsubscribe.turn_off("acct-1", utcnow())

        assert await wants_job_emails("acct-2") is True

    async def test_a_link_issued_after_the_last_change_turns_mail_off(
        self, setup_database
    ):
        await set_job_emails("acct-1", True)

        assert await job_mail_unsubscribe.turn_off("acct-1", utcnow()) is True
        assert await wants_job_emails("acct-1") is False

    async def test_using_a_link_twice_leaves_mail_off(self, setup_database):
        issued_at = utcnow()
        await job_mail_unsubscribe.turn_off("acct-1", issued_at)

        assert await job_mail_unsubscribe.turn_off("acct-1", issued_at) is True
        assert await wants_job_emails("acct-1") is False

    async def test_a_reused_link_cannot_undo_turning_mail_back_on(self, setup_database):
        """The abuse case: someone holding an old mail keeps switching the owner's mail off."""
        issued_at = utcnow() - timedelta(minutes=5)
        await job_mail_unsubscribe.turn_off("acct-1", issued_at)
        await set_job_emails("acct-1", True)

        assert await job_mail_unsubscribe.turn_off("acct-1", issued_at) is False
        assert await wants_job_emails("acct-1") is True

    async def test_a_link_built_in_the_millisecond_of_a_change_cannot_undo_it(
        self, setup_database
    ):
        await set_job_emails("acct-1", True)
        stored = await NotificationPreference.find_one(
            NotificationPreference.user_id == "acct-1"
        )
        assert stored is not None
        link = job_mail_unsubscribe.read(
            job_mail_unsubscribe.token_for("acct-1", as_utc(stored.updated_at))
        )
        assert link is not None

        assert await job_mail_unsubscribe.turn_off("acct-1", link.issued_at) is False
        assert await wants_job_emails("acct-1") is True

    async def test_it_keeps_one_row_per_account(self, setup_database):
        await job_mail_unsubscribe.turn_off("acct-1", utcnow())
        await job_mail_unsubscribe.turn_off("acct-1", utcnow())

        rows = await NotificationPreference.find(
            NotificationPreference.user_id == "acct-1"
        ).to_list()
        assert [row.job_emails for row in rows] == [False]
