"""#608: a column's name must not lower its PII risk.

The detector used to `continue` after a column-name hit, so the values of the
honestly-named column were never examined; the name-only confidence (0.8) sat
exactly on the report's `> 0.8` high-risk boundary and could never be high.
"""

import pandas as pd
import pytest

from app.services.security.pii_detector import (
    HIGH_RISK_CONFIDENCE,
    NAME_MATCH_CONFIDENCE,
    PIIDetector,
    PIIType,
)

SSNS = ["123-45-6789", "987-65-4321", "111-22-3333", "222-33-4444"]


def _risk(column_name: str, values: list[str]) -> str:
    detector = PIIDetector()
    detections = detector.detect_pii_in_dataframe(pd.DataFrame({column_name: values}))
    return detector.generate_pii_report(detections)["risk_level"]


@pytest.mark.parametrize("column_name", ["ssn", "identifier", "ref_code", "social_security_number"])
def test_identical_ssn_values_are_rated_the_same_whatever_the_column_is_called(column_name):
    assert _risk(column_name, SSNS) == "high"


def test_an_ssn_column_of_ssns_yields_one_detection_carrying_the_stronger_signal():
    detections = PIIDetector().detect_pii_in_dataframe(pd.DataFrame({"ssn": SSNS}))
    assert len(detections) == 1
    assert detections[0].pii_type == PIIType.SSN
    assert detections[0].confidence > HIGH_RISK_CONFIDENCE
    assert detections[0].sample_count == len(SSNS)


def test_a_pii_name_over_non_pii_values_stays_medium():
    # A label is a hint, not proof: nothing in the values matches any pattern.
    assert _risk("ssn", ["alpha", "beta", "gamma", "delta"]) == "medium"


def test_the_boundary_is_a_deliberate_constant():
    assert NAME_MATCH_CONFIDENCE <= HIGH_RISK_CONFIDENCE  # name-only can never be high
    assert _risk("customer_email", ["not-an-email"] * 4) == "medium"


def test_a_weak_value_signal_does_not_override_a_name_match():
    # One e-mail in four: the pattern says 0.25, the name says 0.8 — keep the name,
    # and the column is still medium (a hint plus a whisper is not evidence).
    detections = PIIDetector().detect_pii_in_dataframe(
        pd.DataFrame({"customer_email": ["a@x.test", "n/a", "n/a", "n/a"]})
    )
    assert len(detections) == 1
    assert detections[0].confidence == NAME_MATCH_CONFIDENCE
    assert detections[0].sample_count == 0


def test_on_an_exact_tie_the_values_win():
    # 4 of 5 values match → pattern confidence 0.8, equal to the name's; the
    # pattern detection is kept (type from the values, sample_count from them).
    detections = PIIDetector().detect_pii_in_dataframe(
        pd.DataFrame({"ssn": SSNS + ["n/a"]})
    )
    assert len(detections) == 1
    assert detections[0].confidence == NAME_MATCH_CONFIDENCE
    assert detections[0].sample_count == 4  # came from the value check, not the name


def test_when_name_and_values_disagree_the_values_name_the_type():
    detections = PIIDetector().detect_pii_in_dataframe(pd.DataFrame({"phone": SSNS}))
    assert len(detections) == 1
    assert detections[0].pii_type == PIIType.SSN
    assert detections[0].confidence > HIGH_RISK_CONFIDENCE
