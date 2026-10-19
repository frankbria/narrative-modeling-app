"""The figures the public /security page states are the ones the code uses (#772).

The page reads `apps/frontend/lib/trust/datasetFacts.ts`; each constant is held to the
backend line it describes, so a change here fails instead of leaving the page stale.
"""

import inspect
import re
from pathlib import Path

from app.services.security.pii_detector import PIIDetector
from app.utils.s3 import dataset_s3_key

REPO = Path(__file__).resolve().parents[4]
FACTS = (REPO / "apps/frontend/lib/trust/datasetFacts.ts").read_text()
SUMMARIZATION = (REPO / "apps/backend/app/services/dataset_summarization.py").read_text()


def fact(name: str) -> str:
    match = re.search(rf"export const {name} = '?([\w-]+)'?", FACTS)
    assert match, f"{name} is not exported by datasetFacts.ts"
    return match.group(1)


def test_a_dataset_is_stored_under_the_prefix_the_page_states():
    assert dataset_s3_key("acct1", "my data.csv").startswith(f"{fact('DATASET_KEY_PREFIX')}/acct1/")


def test_the_pii_scan_reads_the_number_of_values_the_page_states():
    default = inspect.signature(PIIDetector.detect_pii_in_dataframe).parameters["sample_size"].default
    assert default == int(fact("PII_SCAN_SAMPLE_ROWS"))


def test_the_summary_sends_the_number_of_sample_rows_the_page_states():
    assert f"sample_data[:{fact('AI_SAMPLE_ROWS')}]" in SUMMARIZATION
