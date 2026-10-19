"""#1102: `_s3_key` — what an erasure deletes for each shape a stored location can take."""
import pytest

from app.schemas.erasure import DeletionManifest
from app.services.erasure_service import _s3_key

BUCKET = "ours"


def _manifest() -> DeletionManifest:
    return DeletionManifest(target_type="dataset", target_id="d", subject_user_id="u")


@pytest.mark.parametrize(
    ("stored", "key"),
    [
        (None, None),
        ("", None),
        ("datasets/u/abc.csv", "datasets/u/abc.csv"),
        ("notes http://x.csv", "notes http://x.csv"),  # a legacy client-filename key
        ("what?.csv", "what?.csv"),
        ("s3://ours/datasets/u/abc.csv", "datasets/u/abc.csv"),
        ("https://ours.s3.amazonaws.com/datasets/u/abc.csv?X-Amz-Signature=1", "datasets/u/abc.csv"),
        ("s3://ours/", None),  # a URL with no key
    ],
)
def test_the_key_each_stored_location_resolves_to(stored, key):
    assert _s3_key(stored, BUCKET) == key


def test_a_url_naming_another_bucket_is_skipped_and_recorded():
    manifest = _manifest()

    assert _s3_key("s3://theirs/datasets/u/abc.csv", BUCKET, manifest) is None
    assert len(manifest.failures) == 1
    assert "'theirs'" in manifest.failures[0] and "'ours'" in manifest.failures[0]


def test_a_url_naming_another_bucket_without_a_manifest_is_still_skipped():
    assert _s3_key("s3://theirs/datasets/u/abc.csv", BUCKET) is None
