"""#494 AC3: an account reads and changes whether it is mailed when a job ends."""

from app.models.notification_preference import NotificationPreference

URL = "/api/v1/users/me/notification-preferences"
TEST_USER = "test_user_123"


async def test_the_default_is_on(async_authorized_client, setup_database):
    response = await async_authorized_client.get(URL)

    assert response.status_code == 200
    assert response.json() == {"job_emails": True}


async def test_turning_it_off_is_stored_for_the_caller(async_authorized_client, setup_database):
    response = await async_authorized_client.put(URL, json={"job_emails": False})

    assert response.status_code == 200
    assert response.json() == {"job_emails": False}
    stored = await NotificationPreference.find_one(NotificationPreference.user_id == TEST_USER)
    assert stored is not None and stored.job_emails is False
    assert (await async_authorized_client.get(URL)).json() == {"job_emails": False}


async def test_another_accounts_choice_is_not_the_callers(async_authorized_client, setup_database):
    await NotificationPreference(user_id="someone-else", job_emails=False).insert()

    assert (await async_authorized_client.get(URL)).json() == {"job_emails": True}


async def test_a_body_without_the_choice_is_refused(async_authorized_client, setup_database):
    response = await async_authorized_client.put(URL, json={"emails": False})

    assert response.status_code == 422
    assert await NotificationPreference.find_one(NotificationPreference.user_id == TEST_USER) is None
