"""#494: a test run cannot send mail, whatever the developer's .env holds.

`app.config` loads `apps/backend/.env` without override, so a developer's `RESEND_API_KEY`
would otherwise make every job the suite finishes send a real message. `tests/conftest.py`
pins the key and the sender to nothing before any app import, as it does the OpenAI key
(#1089); a test that wants a configured sender sets both and replaces `_client`.
"""

import os

from app.services import email_service


def test_the_suite_carries_no_resend_key():
    assert os.environ["RESEND_API_KEY"] == ""
    assert os.environ["EMAIL_FROM"] == ""


def test_the_suite_cannot_send():
    assert email_service.is_configured() is False
