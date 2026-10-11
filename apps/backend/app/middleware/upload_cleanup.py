"""Delete an object a failed request uploaded and nothing ended up owning (#735).

Every upload route writes the S3 object before the document that points at it. When
schema inference, validation or the insert then failed, the request answered an error
and the quota was refunded, but the object stayed in the bucket with no owner. Erasure
walks documents, so it could never reach it.

One place rather than a `try/except` in each route, like `QuotaRefundMiddleware`: routes
get added, and the one that forgets orphans silently. `upload_file_to_s3` records what
it writes; this deletes what no document references once the request has failed.
"""

import logging
import re
from urllib.parse import quote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.models.bulk_transformation import BulkTransformationJob
from app.models.dataset import DatasetMetadata
from app.models.transformation import TransformationConfig
from app.models.user_data import UserData
from app.services.s3_service import s3_service
from app.utils.s3 import record_request_uploads

logger = logging.getLogger(__name__)

# Every field that can name a dataset's object, current or not.
_OWNERS = (
    (UserData, ("s3_url", "file_path", "superseded_s3_urls")),
    (DatasetMetadata, ("s3_url", "file_path", "source_s3_url", "superseded_s3_urls")),
    # Written before the dataset itself moves to a transformed file.
    (TransformationConfig, ("current_file_path",)),
    (BulkTransformationJob, ("output_file_path",)),
)


class UnownedUploadCleanupMiddleware(BaseHTTPMiddleware):
    """On a 4xx/5xx or an unhandled exception, delete the objects this request wrote
    that no document references.

    A 2xx keeps everything, including a 2xx that reports failure in its body. A request
    cancelled by a client disconnect is not cleaned up either;
    `scripts/inventory_orphaned_s3_objects.py` reports what is left.
    """

    async def dispatch(self, request: Request, call_next):
        uploads = record_request_uploads()
        try:
            response = await call_next(request)
        except Exception:
            await _delete_unowned(uploads)
            raise

        if response.status_code >= 400:
            await _delete_unowned(uploads)
        return response


async def _delete_unowned(keys: list[str]) -> None:
    # Emptied first: an exception path can reach this twice otherwise.
    pending, keys[:] = list(keys), []
    for key in pending:
        try:
            if not await _is_referenced(key):
                await s3_service.delete_file(key)
                # The key, as the upload's own log line gives it: this is the only
                # record that the object existed.
                logger.warning("Deleted an object a failed request uploaded and left unowned: %s", key)
        except Exception:
            # Left in place: an orphan is reported by the inventory script, while a
            # deleted object that a row still points at is the customer's file gone.
            logger.exception(
                "Could not clean up an object a failed request uploaded; it may be orphaned: %s", key
            )


async def _is_referenced(key: str) -> bool:
    """Whether any document names this object.

    Asked of the database, not inferred from where the request failed: an insert can
    land and then raise, and `/datasets/upload` writes two documents.
    """
    # A stored location is the bare key, a URL ending in it, or a presigned URL, which
    # percent-encodes the key and appends `?…`.
    # shortcut: unindexed regexes on the failure path only; store a normalised key and
    # index it if failed uploads ever become frequent.
    spellings = "|".join(sorted({re.escape(key), re.escape(quote(key))}))
    names_key = {"$regex": f"({spellings})(\\?|$)"}
    for model, fields in _OWNERS:
        if await model.find_one({"$or": [{field: names_key} for field in fields]}) is not None:
            return True
    return False
