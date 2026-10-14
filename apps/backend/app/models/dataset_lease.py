"""A lease on work that must not run twice at once for one dataset (#853).

The holder is whichever request inserted the document: `_id` is the lease's name, and
`_id` is unique in every collection, so "one holder at a time" needs no index of its
own and holds across the container's workers. See `app/services/dataset_lease.py`.
"""

from datetime import datetime

from beanie import Document
from pymongo import ASCENDING, IndexModel


class DatasetLease(Document):
    id: str  # type: ignore[assignment]  # the lease's name, not an ObjectId
    holder: str
    expires_at: datetime

    class Settings:
        name = "dataset_leases"
        indexes = [
            # A holder that died never deletes its lease: Mongo sweeps it once it expires.
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="expires_at_ttl"),
        ]
