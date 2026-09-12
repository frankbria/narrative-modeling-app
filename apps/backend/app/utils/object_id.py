"""Coerce request ids to the ObjectId that `Document.id` actually stores (#465).

`UserData.id` is a `PydanticObjectId`. Comparing it to the raw string from a path or
body — `UserData.id == file_id`, or `{"_id": request.dataset_id}` in a raw dict —
builds `{"_id": "<string>"}`, which can never match, so the route answers a permanent
404 for a document that exists. `Document.get(str)` is coerced by Beanie itself; every
other query shape must go through here.
"""
from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status


def require_object_id(value: str, what: str = "id") -> PydanticObjectId:
    """The ObjectId for `value`, or a 400 naming the parameter when it is not one."""
    try:
        return PydanticObjectId(value)
    except (InvalidId, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {what}: not a valid identifier",
        ) from None
