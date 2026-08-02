"""Null-tolerance in the statistics highlights (#409).

`_extract_statistical_highlights` compared stored values against numbers with
`.get(key, default)`, which returns the default only when the key is **absent** —
not when it exists holding null. Real documents store nulls in exactly these two
places:

* categorical columns get `outlier_count: null` (outliers are not a concept there)
* non-numeric pairs get a null correlation

so `None > 0` and `abs(None)` raised, the service swallowed it, and the whole
summary degraded to its "Failed to generate dataset summary" card. Any dataset
with a single categorical column was affected — which is nearly all of them.

Reproduced against a real 1,000-row upload: 5 of 10 columns had
`outlier_count: None`, and the AI Insights panel showed the error card even after
its routing and lookup bugs were fixed.
"""

from app.services.dataset_summarization import dataset_summarization_service


def _highlights(statistics: dict):
    return dataset_summarization_service._extract_statistical_highlights(statistics)


class TestStatisticalHighlightsNullTolerance:
    def test_categorical_columns_with_null_outlier_count_do_not_raise(self):
        stats = {
            "column_statistics": [
                {"column_name": "contract_type", "outlier_count": None},
                {"column_name": "age", "outlier_count": 3, "outlier_percentage": 0.3},
            ],
        }

        highlights = _highlights(stats)

        # The null column is skipped, the real one is still reported.
        assert [c["column"] for c in highlights["outlier_columns"]] == ["age"]

    def test_zero_outliers_are_still_excluded(self):
        stats = {"column_statistics": [{"column_name": "age", "outlier_count": 0}]}

        assert _highlights(stats)["outlier_columns"] == []

    def test_null_correlations_do_not_raise(self):
        stats = {
            "correlation_matrix": {
                "age": {"age": 1.0, "city": None, "income": 0.83},
                "income": {"age": 0.83, "city": None, "income": 1.0},
                "city": {"age": None, "income": None, "city": None},
            },
        }

        pairs = [tuple(c["columns"]) for c in _highlights(stats)["correlations"]]

        assert ("age", "income") in pairs
        assert all(None not in p for p in pairs)

    def test_a_realistic_mixed_document_produces_highlights(self):
        """The shape that actually broke: numeric + categorical side by side."""
        stats = {
            "column_statistics": [
                {"column_name": "age", "outlier_count": 12, "outlier_percentage": 1.2},
                {"column_name": "contract_type", "outlier_count": None},
                {"column_name": "has_phone", "outlier_count": None},
            ],
            "correlation_matrix": {
                "age": {"age": 1.0, "tenure": 0.91, "contract_type": None},
                "tenure": {"age": 0.91, "tenure": 1.0, "contract_type": None},
            },
        }

        highlights = _highlights(stats)

        assert [c["column"] for c in highlights["outlier_columns"]] == ["age"]
        assert [tuple(c["columns"]) for c in highlights["correlations"]] == [
            ("age", "tenure"),
            ("tenure", "age"),
        ]
