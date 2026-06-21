"""Model versioning and history tracking (issue #78).

Builds version history on top of the existing ``MLModel`` document rather than a
separate version collection. A **version family** is all models a user trained
on the same dataset under the same name — ``(user_id, dataset_id, name)``. Within
a family, versions are ordered by ``created_at`` (oldest = version 1) and exactly
one may be flagged ``is_production``.

Promotion sets ``is_production`` on the target and clears it on its siblings;
**rollback is just promoting an older version**, so a single ``promote`` covers
both acceptance criteria.
"""

from __future__ import annotations

import importlib
import platform
from datetime import UTC, datetime

from beanie.odm.operators.update.general import Set

from app.models.ml_model import MLModel
from app.services.exceptions import NotFoundError


def capture_environment() -> dict[str, str]:
    """Capture the runtime environment for reproducibility (best-effort).

    Records python/platform plus the versions of the ML libraries actually
    installed. Any library that can't be imported is simply omitted.
    """
    env: dict[str, str] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    for lib in ("sklearn", "xgboost", "lightgbm", "numpy"):
        try:
            module = importlib.import_module(lib)
            env[lib] = getattr(module, "__version__", "unknown")
        except Exception:
            continue
    return env


class ModelVersioningService:
    """Version-aware operations over ``MLModel`` documents."""

    async def get_model(self, model_id: str, user_id: str) -> MLModel | None:
        """Fetch a single owned model, or ``None`` if unknown/foreign."""
        return await MLModel.find_one(
            MLModel.model_id == model_id, MLModel.user_id == user_id
        )

    async def list_family(self, model_id: str, user_id: str) -> list[MLModel]:
        """Return the model's version family, oldest first.

        Raises ``NotFoundError`` when the anchor model is unknown or owned by
        another user.
        """
        anchor = await self.get_model(model_id, user_id)
        if anchor is None:
            raise NotFoundError(
                resource_type="Model", resource_id=model_id, code="MODEL_NOT_FOUND"
            )
        return await self._family_query(user_id, anchor.dataset_id, anchor.name)

    async def get_production_version(
        self, user_id: str, dataset_id: str, name: str
    ) -> MLModel | None:
        """Current production version of a family, if one is promoted."""
        return await MLModel.find_one(
            MLModel.user_id == user_id,
            MLModel.dataset_id == dataset_id,
            MLModel.name == name,
            MLModel.is_production == True,  # noqa: E712 (Beanie needs ==)
        )

    async def resolve_parent(
        self, user_id: str, dataset_id: str, name: str
    ) -> str | None:
        """The most recent existing family member's ``model_id``.

        Used at training time to chain a new version onto the previous one
        (``parent_model_id``). ``None`` when this is the family's first version.
        """
        family = await self._family_query(user_id, dataset_id, name)
        return family[-1].model_id if family else None

    async def promote_to_production(
        self, model_id: str, user_id: str
    ) -> tuple[MLModel, list[str]]:
        """Promote a version to production, demoting its siblings.

        Returns the promoted model and the list of demoted model ids. Idempotent:
        re-promoting the current production version is a no-op that still returns
        it. Rolling back = calling this on an older version.
        """
        family = await self.list_family(model_id, user_id)
        target = next((m for m in family if m.model_id == model_id), None)
        if target is None:  # anchor deleted between the two reads in list_family
            raise NotFoundError(
                resource_type="Model", resource_id=model_id, code="MODEL_NOT_FOUND"
            )
        demoted = [
            m.model_id
            for m in family
            if m.model_id != model_id and m.is_production
        ]

        # Idempotent no-op: target already the sole production version.
        if target.is_production and not demoted:
            return target, demoted

        # Demote the whole family in one bulk write, then promote the target.
        # Beta limitation: two concurrent promotions are last-writer-wins (the
        # same accepted limitation as #87 workflow state — a serialized
        # demote+promote would need a Mongo transaction, which needs a replica
        # set we don't run in tests). The bulk demote keeps the window tiny, but
        # if a second promote lands between this demote and the target save below,
        # two members can briefly carry is_production=True; the version browser
        # then reports whichever appears first by created_at as production_model_id.
        await MLModel.find(
            MLModel.user_id == user_id,
            MLModel.dataset_id == target.dataset_id,
            MLModel.name == target.name,
            MLModel.is_production == True,  # noqa: E712 (Beanie needs ==)
        ).update(Set({MLModel.is_production: False}))

        target.is_production = True
        target.promoted_at = datetime.now(UTC)
        await target.save()
        return target, demoted

    async def _family_query(
        self, user_id: str, dataset_id: str, name: str
    ) -> list[MLModel]:
        """All models in a family, ordered oldest → newest by ``created_at``."""
        return (
            await MLModel.find(
                MLModel.user_id == user_id,
                MLModel.dataset_id == dataset_id,
                MLModel.name == name,
            )
            .sort("+created_at")
            .to_list()
        )


# Singleton, mirroring ``versioning_service = VersioningService()``.
model_versioning_service = ModelVersioningService()
