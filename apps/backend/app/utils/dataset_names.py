"""Dataset display names for list responses, so the UI never shows a raw id (#1175)."""
from beanie import PydanticObjectId
from bson.errors import InvalidId

from app.models.user_data import UserData


def _object_id_or_none(value: str) -> PydanticObjectId | None:
    try:
        return PydanticObjectId(value)
    except (InvalidId, ValueError, TypeError):
        return None


async def dataset_names(user_id: str, dataset_ids: set[str]) -> dict[str, str]:
    """``{dataset_id: filename}`` for the user's datasets that still exist."""
    object_ids = [oid for d in dataset_ids if (oid := _object_id_or_none(d))]
    if not object_ids:
        return {}
    docs = await UserData.find({"user_id": user_id, "_id": {"$in": object_ids}}).to_list()
    return {str(doc.id): doc.filename for doc in docs}
