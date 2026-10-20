"""The figures the public /security page states are the ones the code uses (#772).

The page reads `apps/frontend/lib/trust/datasetFacts.ts`; each constant is held to the
backend line it describes, so a change here fails instead of leaving the page stale.
"""

import inspect
import re
from pathlib import Path

import pandas as pd

from app.models.training_job import TrainingJob
from app.services.dataset_service import DatasetService
from app.services.erasure_service import _STRING_KEYED_MODELS, DatasetErasureService
from app.services.security.pii_detector import PIIDetector
from app.utils.ai_summary import prepare_dataset_summary_from_df
from app.utils.s3 import dataset_s3_key

REPO = Path(__file__).resolve().parents[4]
FACTS = (REPO / "apps/frontend/lib/trust/datasetFacts.ts").read_text()
SUMMARIZATION = (REPO / "apps/backend/app/services/dataset_summarization.py").read_text()


def fact(name: str) -> str:
    match = re.search(rf"export const {name} = (?:'([^']*)'|(\d+))\s*$", FACTS, re.MULTILINE)
    assert match, f"{name} is not exported by datasetFacts.ts"
    return match.group(1) or match.group(2)


def fact_list(name: str) -> set[str]:
    match = re.search(rf"export const {name} = \[([^\]]*)\]", FACTS)
    assert match, f"{name} is not exported by datasetFacts.ts"
    return set(re.findall(r"'([^']+)'", match.group(1)))


def key_pattern(template: str) -> re.Pattern[str]:
    """The template with its placeholders as the regex the real key must match."""
    uuid = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    escaped = re.escape(template)
    for placeholder, regex in (
        (r"<account\ id>", "acct1"),
        (r"<random\ id>", uuid),
        (r"<extension>", "csv"),
    ):
        escaped = escaped.replace(placeholder, regex)
    return re.compile(f"^{escaped}$")


def test_a_dataset_is_stored_at_the_key_shape_the_page_states():
    assert key_pattern(fact("DATASET_KEY_TEMPLATE")).match(dataset_s3_key("acct1", "my data.csv"))


def test_a_masked_copy_is_stored_at_the_key_shape_the_page_states():
    key = dataset_s3_key("acct1", "masked.csv", masked=True)
    assert key_pattern(fact("MASKED_KEY_TEMPLATE")).match(key)


def test_the_pii_scan_reads_the_number_of_values_the_page_states():
    default = inspect.signature(PIIDetector.detect_pii_in_dataframe).parameters["sample_size"].default
    assert default == int(fact("PII_SCAN_SAMPLE_ROWS"))


def test_the_scan_checks_the_value_categories_and_name_categories_the_page_lists():
    detector = PIIDetector()
    assert {t.value for t in detector.patterns} == fact_list("PII_VALUE_CATEGORIES")
    assert {t.value for t in detector.name_patterns} == fact_list("PII_NAME_CATEGORIES")


def test_the_upload_summary_sends_the_number_of_example_values_the_page_states():
    """Both summary paths read the same inferred schema, which keeps this many per column."""
    df = pd.DataFrame({"city": [f"town{i}" for i in range(50)]})
    summary = prepare_dataset_summary_from_df(df, "f.csv")
    assert len(summary["columns"][0]["example_values"]) == int(fact("SUMMARY_EXAMPLE_VALUES"))
    assert summary["filename"] == "f.csv"


def test_deleting_a_dataset_erases_the_models_trained_on_it_as_the_policy_states():
    """Privacy section 6 and the trust page say a dataset's deletion removes its models (#1111)."""
    assert "await self._erase_models(dataset_id, user_id, manifest)" in inspect.getsource(
        DatasetErasureService._erase_keyed_children
    )
    models = inspect.getsource(DatasetErasureService._erase_models)
    assert "MLModel.dataset_id == dataset_id" in models
    assert "self.model_storage.delete_model(" in models  # the saved model files
    assert "PredictionEvent" in models and "_erase_batch_jobs" in models
    assert TrainingJob in _STRING_KEYED_MODELS
    assert "dataset_erasure_service.erase_dataset(" in inspect.getsource(DatasetService.delete_dataset)


def test_the_explore_panel_sends_the_number_of_sample_rows_the_page_states():
    assert f"sample_data[:{fact('AI_SAMPLE_ROWS')}]" in SUMMARIZATION
