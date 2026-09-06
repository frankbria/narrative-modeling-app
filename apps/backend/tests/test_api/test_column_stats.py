"""Route tests for the column-statistics API (issue #449).

`column_stats.py` had no route tests at all, which is how the cache-hit
authorization bypass survived two adversarial review panels: every test of this
surface exercised the compute path, where the ownership check lives.

These use `async_authorized_client` (the full app with auth overridden) and real
Mongo documents — `mock_async_client` mounts only two routers, so a test written
against it would 404 vacuously and prove nothing (see CLAUDE.md, #267).
"""

import pytest
from beanie import PydanticObjectId
from httpx import AsyncClient

from app.models.column_stats import ColumnStats
from app.models.user_data import UserData

OTHER_USER = "other_user_449"


async def make_user_data(user_id: str) -> UserData:
    """A minimal persisted UserData owned by `user_id`."""
    dataset = UserData(
        user_id=user_id,
        filename="payroll.csv",
        original_filename="payroll.csv",
        s3_url=f"s3://test-bucket/{user_id}/payroll.csv",
        file_path=f"{user_id}/payroll.csv",
        num_rows=100,
        num_columns=2,
        data_schema=[],
    )
    await dataset.insert()
    return dataset


async def seed_cached_stats(
    dataset: UserData, owner_id: str, column_name: str = "salary"
) -> None:
    """Insert a ColumnStats row the route's cache query actually matches.

    The route queries `ColumnStats.dataset_id == PydanticObjectId(...)`, while
    Beanie's `Link` write path stores a DBRef — so a normally-created row never
    matches (that mismatch is #543). Writing the bare ObjectId directly is what
    makes the cache genuinely hit, which is the only way to exercise the bypass
    this issue is about, and it is the shape #543 will produce once fixed.
    """
    await ColumnStats.get_motor_collection().insert_one(
        {
            "dataset_id": dataset.id,
            "user_id": owner_id,
            "column_name": column_name,
            "data_type": "numeric",
            "count": 100,
            "missing": 0,
            "unique": 97,
            "min_value": 31000.0,
            "max_value": 480000.0,
            "mean": 118000.0,
        }
    )


@pytest.mark.integration
class TestColumnStatsTenantIsolation:
    """The ownership check must not depend on the cache being cold."""

    @pytest.mark.asyncio
    async def test_cached_stats_of_another_tenant_are_not_returned(
        self, async_authorized_client: AsyncClient, setup_database
    ):
        """The bug: on a cache hit the handler returned foreign stats untouched."""
        # ARRANGE
        victim_dataset = await make_user_data(OTHER_USER)
        await seed_cached_stats(victim_dataset, OTHER_USER)

        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/column_stats/dataset/{victim_dataset.id}"
        )

        # ASSERT
        assert response.status_code == 404
        assert "salary" not in response.text
        assert "480000" not in response.text

    @pytest.mark.asyncio
    async def test_uncached_stats_of_another_tenant_return_404_not_500(
        self, async_authorized_client: AsyncClient, setup_database
    ):
        """Cache-miss path: the ownership rejection is currently raised inside a
        bare `except Exception`, so it surfaces as 500 rather than a refusal."""
        # ARRANGE
        victim_dataset = await make_user_data(OTHER_USER)

        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/column_stats/dataset/{victim_dataset.id}"
        )

        # ASSERT
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_owner_still_gets_their_cached_stats(
        self, async_authorized_client: AsyncClient, setup_database, mock_user_id: str
    ):
        """Regression guard: scoping the cache must not break the owner path."""
        # ARRANGE
        mine = await make_user_data(mock_user_id)
        await seed_cached_stats(mine, mock_user_id)

        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/column_stats/dataset/{mine.id}"
        )

        # ASSERT
        assert response.status_code == 200
        assert [c["column_name"] for c in response.json()] == ["salary"]

    @pytest.mark.asyncio
    async def test_scoped_cache_read_excludes_a_foreign_row_on_your_own_dataset(
        self, async_authorized_client: AsyncClient, setup_database, mock_user_id: str
    ):
        """AC2, independently of AC1.

        The caller owns this dataset, so the ownership check passes either way.
        Only the owner predicate on the cache query itself can stop a stray
        foreign-owned stats row from being served — which is what AC2 asks for
        ("even if the check above is later refactored away").
        """
        # ARRANGE
        mine = await make_user_data(mock_user_id)
        await seed_cached_stats(mine, mock_user_id, column_name="salary")
        await seed_cached_stats(mine, OTHER_USER, column_name="ssn")

        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/column_stats/dataset/{mine.id}"
        )

        # ASSERT
        assert response.status_code == 200
        assert [c["column_name"] for c in response.json()] == ["salary"]
        assert "ssn" not in response.text

    @pytest.mark.asyncio
    async def test_malformed_dataset_id_is_404_not_500(
        self, async_authorized_client: AsyncClient, setup_database
    ):
        """`PydanticObjectId("not-an-id")` raises; that must not be a 500."""
        # ACT
        response = await async_authorized_client.get(
            "/api/v1/column_stats/dataset/not-an-object-id"
        )

        # ASSERT
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_recalculate_on_another_tenants_dataset_is_refused(
        self, async_authorized_client: AsyncClient, setup_database
    ):
        """The sibling handler answers 403 today, which confirms the dataset
        exists. Same answer as an unknown dataset is the correct one."""
        # ARRANGE
        victim_dataset = await make_user_data(OTHER_USER)
        await seed_cached_stats(victim_dataset, OTHER_USER)

        # ACT
        response = await async_authorized_client.post(
            f"/api/v1/column_stats/dataset/{victim_dataset.id}/recalculate"
        )

        # ASSERT
        assert response.status_code == 404
        # and the victim's cached row is untouched
        assert await ColumnStats.get_motor_collection().count_documents(
            {"dataset_id": PydanticObjectId(str(victim_dataset.id))}
        ) == 1
