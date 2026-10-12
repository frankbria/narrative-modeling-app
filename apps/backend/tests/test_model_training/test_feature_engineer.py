"""
Tests for feature engineering
"""

import pickle

import numpy as np
import pandas as pd
import pytest

from app.services.model_export_assets._standalone_fe import StandaloneFeatureEngineer
from app.services.model_export_runtime import feature_engineer_state
from app.services.model_training.feature_engineer import (
    FeatureEngineer,
    FeatureEngineeringConfig,
    FeatureEngineeringResult,
)


class TestFeatureEngineer:
    """Test suite for feature engineering"""
    
    @pytest.fixture
    def config(self):
        """Create feature engineering config"""
        return FeatureEngineeringConfig(
            handle_missing=True,
            scale_features=True,
            encode_categorical=True,
            create_interactions=False,
            select_features=True,
            max_features=10
        )
    
    @pytest.fixture
    def engineer(self, config):
        """Create feature engineer instance"""
        return FeatureEngineer(config)
    
    @pytest.fixture
    def mixed_data(self):
        """Create dataset with mixed types and missing values"""
        np.random.seed(42)
        n_samples = 100
        return pd.DataFrame({
            'numeric1': np.random.randn(n_samples),
            'numeric2': np.random.randn(n_samples),
            'numeric3': np.concatenate([np.random.randn(90), [np.nan] * 10]),
            'categorical1': np.random.choice(['A', 'B', 'C'], n_samples),
            'categorical2': np.concatenate([
                np.random.choice(['X', 'Y', 'Z'], 95),
                [np.nan] * 5
            ]),
            'numeric_categorical': np.random.choice([0, 1, 2, 3], n_samples)  # 4 values < 5% threshold
        })
    
    @pytest.fixture
    def target_classification(self):
        """Create classification target"""
        np.random.seed(42)
        return pd.Series(np.random.choice([0, 1], 100))
    
    @pytest.fixture
    def target_regression(self):
        """Create regression target"""
        np.random.seed(42)
        return pd.Series(np.random.randn(100) * 10 + 50)
    
    @pytest.mark.asyncio
    async def test_identify_feature_types(self, engineer, mixed_data):
        """Test feature type identification"""
        engineer._identify_feature_types(mixed_data)
        
        # Check numeric features (numeric_categorical should be moved to categorical)
        assert set(engineer.numeric_features) == {'numeric1', 'numeric2', 'numeric3'}
        
        # Check categorical features
        assert set(engineer.categorical_features) == {
            'categorical1', 'categorical2', 'numeric_categorical'
        }

    @pytest.mark.asyncio
    async def test_boolean_columns_treated_as_categorical(self):
        """Boolean columns (parsed from true/false CSV values) must become
        categorical and survive a string-valued transform — otherwise they
        are silently dropped from the prediction form/contract (issue #82)."""
        config = FeatureEngineeringConfig(
            select_features=False, create_interactions=False, scale_features=False
        )
        engineer = FeatureEngineer(config)
        df = pd.DataFrame(
            {
                'num': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                'flag': [True, False, True, False, True, False],
            }
        )
        y = pd.Series([0, 1, 0, 1, 0, 1])

        result = await engineer.fit_transform(df, y, 'binary_classification')

        assert 'flag' in engineer.categorical_features
        assert 'flag' not in engineer.numeric_features
        # The raw bool column is encoded away in the engineered feature set.
        assert 'flag' not in result.feature_names

        # The form submits categorical values as strings; transform must accept
        # "True"/"False" and match the encoder categories fitted from bools.
        out = await engineer.transform(pd.DataFrame([{'num': 2.5, 'flag': 'True'}]))
        assert len(out) == 1
        # Engineered output should not still carry a raw bool 'flag' column.
        assert 'flag' not in out.columns
    
    @pytest.mark.asyncio
    async def test_handle_missing_values(self, engineer, mixed_data):
        """Test missing value handling"""
        engineer._identify_feature_types(mixed_data)
        
        # Handle missing values
        result = await engineer._handle_missing_values(mixed_data.copy())
        
        # Check no missing values remain
        assert result.isnull().sum().sum() == 0
        
        # Check transformers were saved
        assert 'imputer_numeric' in engineer.transformers
        assert 'imputer_categorical' in engineer.transformers
    
    @pytest.mark.asyncio
    async def test_encode_categorical_onehot(self, engineer, mixed_data):
        """Test one-hot encoding of categorical features"""
        engineer._identify_feature_types(mixed_data)
        engineer.config.encoding_method = "onehot"
        
        # Clean data first
        clean_data = await engineer._handle_missing_values(mixed_data.copy())
        
        # Encode categorical
        result = await engineer._encode_categorical_features(clean_data)
        
        # Check original categorical columns were removed
        for col in engineer.categorical_features:
            assert col not in result.columns
        
        # Check new encoded columns exist
        assert len(result.columns) > len(mixed_data.columns)
        
        # Check encoder was saved
        assert 'encoder' in engineer.transformers
        assert 'encoded_columns' in engineer.transformers
    
    @pytest.mark.asyncio
    async def test_encode_categorical_label(self, engineer, mixed_data):
        """Test label encoding of categorical features"""
        engineer._identify_feature_types(mixed_data)
        engineer.config.encoding_method = "label"
        
        # Clean data first
        clean_data = await engineer._handle_missing_values(mixed_data.copy())
        
        # Encode categorical
        result = await engineer._encode_categorical_features(clean_data)
        
        # Check categorical columns are now numeric
        for col in engineer.categorical_features:
            assert pd.api.types.is_numeric_dtype(result[col])
        
        # Check label encoders were saved
        assert 'label_encoders' in engineer.transformers
        assert len(engineer.transformers['label_encoders']) == len(engineer.categorical_features)
    
    @pytest.mark.asyncio
    async def test_scale_numeric_features(self, engineer, mixed_data):
        """Test numeric feature scaling"""
        engineer._identify_feature_types(mixed_data)
        
        # Clean data first
        clean_data = await engineer._handle_missing_values(mixed_data.copy())
        
        # Scale features
        result = await engineer._scale_numeric_features(clean_data)
        
        # Check scaled values
        for col in engineer.numeric_features:
            # Standard scaling should have mean ~0 and std ~1
            assert abs(result[col].mean()) < 0.1
            assert abs(result[col].std() - 1) < 0.1
        
        # Check scaler was saved
        assert 'scaler' in engineer.transformers
    
    @pytest.mark.asyncio
    async def test_create_interaction_features(self, engineer):
        """Test interaction feature creation"""
        # Create simple numeric data
        df = pd.DataFrame({
            'feature1': [1, 2, 3, 4, 5],
            'feature2': [2, 4, 6, 8, 10],
            'feature3': [1, 1, 1, 1, 1]
        })
        
        engineer.numeric_features = ['feature1', 'feature2', 'feature3']
        engineer.config.create_interactions = True
        
        result = await engineer._create_interaction_features(df.copy())
        
        # Check interaction columns were created
        assert 'feature1_x_feature2' in result.columns
        assert 'feature1_div_feature2' in result.columns
        
        # Check interaction values
        assert list(result['feature1_x_feature2']) == [2, 8, 18, 32, 50]
        
        # Check interaction features were saved
        assert 'interaction_features' in engineer.transformers
    
    @pytest.mark.asyncio
    async def test_select_features_classification(self, engineer, mixed_data, target_classification):
        """Test feature selection for classification"""
        engineer._identify_feature_types(mixed_data)
        
        # Prepare data
        clean_data = await engineer._handle_missing_values(mixed_data.copy())
        encoded_data = await engineer._encode_categorical_features(clean_data)
        
        # Select features
        result, importance = await engineer._select_features(
            encoded_data, target_classification, "classification"
        )
        
        # Check dimensions
        assert result.shape[1] <= engineer.config.max_features
        assert result.shape[1] <= encoded_data.shape[1]
        
        # Check importance scores
        assert importance is not None
        assert len(importance) == result.shape[1]
        assert all(score >= 0 for score in importance.values())
        
        # Check selector was saved
        assert 'selector' in engineer.transformers
        assert 'selected_features' in engineer.transformers
    
    @pytest.mark.asyncio
    async def test_fit_transform_complete_pipeline(self, engineer, mixed_data, target_classification):
        """Test complete fit_transform pipeline"""
        result = await engineer.fit_transform(
            mixed_data,
            target_classification,
            "classification"
        )
        
        # Check result type
        assert isinstance(result, FeatureEngineeringResult)
        
        # Check transformed data
        assert isinstance(result.X_transformed, pd.DataFrame)
        assert result.X_transformed.shape[0] == mixed_data.shape[0]
        assert result.X_transformed.isnull().sum().sum() == 0  # No missing values
        
        # Check feature names
        assert len(result.feature_names) == result.X_transformed.shape[1]
        assert result.feature_names == list(result.X_transformed.columns)
        
        # Check metadata
        assert 'original_features' in result.metadata
        assert 'numeric_features' in result.metadata
        assert 'categorical_features' in result.metadata
        assert result.metadata['final_feature_count'] == len(result.feature_names)
    
    @pytest.mark.asyncio
    async def test_transform_new_data(self, engineer, mixed_data, target_classification):
        """Test transforming new data with fitted engineer"""
        # Fit on training data
        await engineer.fit_transform(
            mixed_data.iloc[:80],
            target_classification.iloc[:80],
            "classification"
        )
        
        # Transform test data
        test_data = mixed_data.iloc[80:].copy()
        result = await engineer.transform(test_data)
        
        # Check result
        assert isinstance(result, pd.DataFrame)
        assert result.shape[0] == test_data.shape[0]
        assert result.shape[1] == len(engineer.feature_names)
        assert list(result.columns) == engineer.feature_names
    
    @pytest.mark.asyncio
    async def test_different_scaling_methods(self, engineer, mixed_data):
        """Test different scaling methods"""
        engineer._identify_feature_types(mixed_data)
        clean_data = await engineer._handle_missing_values(mixed_data.copy())
        
        # Test MinMax scaling
        engineer.config.scaling_method = "minmax"
        result_minmax = await engineer._scale_numeric_features(clean_data.copy())
        
        for col in engineer.numeric_features:
            assert result_minmax[col].min() >= -1e-10  # Allow small numerical errors
            assert result_minmax[col].max() <= 1 + 1e-10
        
        # Test Robust scaling
        engineer.config.scaling_method = "robust"
        engineer.transformers = {}  # Reset transformers
        result_robust = await engineer._scale_numeric_features(clean_data.copy())
        
        # Robust scaling centers on median
        for col in engineer.numeric_features:
            assert abs(result_robust[col].median()) < 0.1
    
    @pytest.mark.asyncio
    async def test_no_feature_selection(self, engineer, mixed_data, target_classification):
        """Test pipeline without feature selection"""
        engineer.config.select_features = False
        
        result = await engineer.fit_transform(
            mixed_data,
            target_classification,
            "classification"
        )
        
        # All features should be kept (after encoding)
        assert 'selector' not in engineer.transformers
        assert result.feature_importance is None
    
    @pytest.mark.asyncio
    async def test_handle_edge_cases(self, engineer):
        """Test handling of edge cases"""
        # Empty dataframe
        empty_df = pd.DataFrame()
        result = await engineer.fit_transform(empty_df)
        assert result.X_transformed.empty
        
        # Single column
        single_col = pd.DataFrame({'col1': [1, 2, 3, 4, 5]})
        result = await engineer.fit_transform(single_col)
        assert result.X_transformed.shape[1] == 1
        
        # All missing values
        all_missing = pd.DataFrame({
            'col1': [np.nan] * 5,
            'col2': [np.nan] * 5
        })
        result = await engineer.fit_transform(all_missing)
        assert result.X_transformed.isnull().sum().sum() == 0

def _churn_frame(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    plan = rng.choice(["basic", "pro", "premium"], n)
    tenure = rng.randint(1, 120, n)
    return pd.DataFrame(
        {
            "age": rng.randint(20, 70, n),
            "tenure": tenure,
            "plan": plan,
            "region": rng.choice(["north", "south", "east", "west"], n),
            "churned": ((plan == "basic") & (tenure < 60)).astype(int),
        }
    )


async def _train_label_encoded():
    """A real AutoML run with label encoding (#697) — no mocks."""
    from app.services.model_training.automl_engine import AutoMLEngine

    engine = AutoMLEngine(max_models=2, cv_folds=2, random_state=0)
    result = await engine.run(
        _churn_frame(200, seed=1),
        "churned",
        FeatureEngineeringConfig(encoding_method="label", select_features=False),
    )
    return engine.feature_engineer, result.best_model.estimator


class TestLabelEncodingAtServing:
    """#697: transform gated the label branch behind "encoder", which label
    encoding never sets — serving fed raw strings to the estimator."""

    @pytest.mark.asyncio
    async def test_held_out_rows_get_the_training_encoding(self):
        fe, model = await _train_label_encoded()
        held_out = _churn_frame(25, seed=2).drop(columns=["churned"])

        out = await fe.transform(held_out)

        assert fe.categorical_features  # the label path actually ran
        for col in fe.categorical_features:
            classes = list(fe.transformers["label_encoders"][col].classes_)
            expected = [classes.index(v) for v in held_out[col].astype(str)]
            assert out[col].tolist() == expected
        assert len(model.predict(out)) == len(held_out)

    @pytest.mark.asyncio
    async def test_unseen_category_is_served_like_a_missing_one(self):
        """An unseen category takes the code a blank cell is imputed to (the
        training mode), not an out-of-range code a model extrapolates from."""
        fe, model = await _train_label_encoded()
        held_out = _churn_frame(3, seed=3).drop(columns=["churned"])
        unseen, blank = held_out.copy(), held_out.copy()
        unseen.loc[0, ["plan", "region"]] = ["enterprise", "mars"]  # never seen at fit
        blank.loc[0, ["plan", "region"]] = [np.nan, np.nan]  # imputed to the training mode

        out = await fe.transform(unseen)

        pd.testing.assert_frame_equal(out, await fe.transform(blank))
        assert out[["plan", "region"]].ge(0).all().all()
        assert len(model.predict(out)) == 3


@pytest.mark.asyncio
async def test_unseen_category_without_an_imputer_falls_back_to_minus_one():
    """With handle_missing off there is no training mode to fall back on."""
    X = pd.DataFrame({"plan": ["a", "b", "a", "b"] * 10, "n": range(40)})
    fe = FeatureEngineer(
        FeatureEngineeringConfig(
            encoding_method="label", handle_missing=False, select_features=False
        )
    )
    await fe.fit_transform(X)

    rows = pd.DataFrame({"plan": ["a", "zzz"], "n": [1, 2]})
    out = await fe.transform(rows)

    assert out["plan"].tolist() == [0, -1]
    standalone = StandaloneFeatureEngineer(feature_engineer_state(fe))
    assert standalone.transform(rows)["plan"].tolist() == [0, -1]

@pytest.mark.asyncio
async def test_integral_floats_and_ints_share_a_label_code():
    """A low-cardinality numeric column fitted as floats (NaNs force float64) must
    still match the same value sent as an int at serving — "1.0" vs "1" would
    silently encode a known category as unseen (#697). The exported standalone
    transform must agree."""
    rng = np.random.RandomState(0)
    tier = rng.choice([1.0, 2.0, 3.0], 120)
    tier[:5] = np.nan
    X = pd.DataFrame({"tier": tier, "plan": rng.choice(["a", "b"], 120)})
    fe = FeatureEngineer(
        FeatureEngineeringConfig(encoding_method="label", select_features=False)
    )
    await fe.fit_transform(X)
    assert "tier" in fe.categorical_features

    classes = list(fe.transformers["label_encoders"]["tier"].classes_)
    standalone = StandaloneFeatureEngineer(pickle.loads(pickle.dumps(feature_engineer_state(fe))))
    for tiers in ([1, 2, 3], [1.0, 2.0, 3.0]):  # served as ints, then as floats
        rows = pd.DataFrame({"tier": tiers, "plan": ["a", "b", "a"]})
        out = await fe.transform(rows)

        assert out["tier"].tolist() == [classes.index(v) for v in ("1", "2", "3")]
        pd.testing.assert_frame_equal(standalone.transform(rows), out, check_dtype=False)


@pytest.mark.parametrize("impl", [FeatureEngineer, StandaloneFeatureEngineer])
def test_label_keys_normalise_numpy_float_scalars(impl):
    """An object column can hold raw np.float32 scalars, which are not Python floats."""
    cells = pd.Series([np.float32(1.0), np.float64(2.0), 3.0, 4, "a", np.nan], dtype=object)
    assert impl._label_keys(cells).tolist() == ["1", "2", "3", "4", "a", "nan"]


def _with_ids(n: int = 200) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.RandomState(0)
    X = pd.DataFrame(
        {
            "customer_id": [f"C{i:05d}" for i in range(n)],
            "row_number": np.arange(1, n + 1),
            "tenure": rng.randint(1, 72, n),
            "monthly_charges": rng.uniform(20, 120, n).round(2),
            "plan": rng.choice(["basic", "pro", "premium"], n),
        }
    )
    y = pd.Series(rng.choice([0, 1], n))
    return X, y


class TestIdentifierColumnsAreExcluded:
    """#806: a per-row identifier is not a feature."""

    async def test_unique_text_and_monotone_numeric_ids_are_excluded_at_fit(self):
        X, y = _with_ids()
        # train_test_split shuffles before the engineer sees the rows; the
        # row-counter check must survive that.
        X, y = X.sample(frac=1, random_state=1), y.sample(frac=1, random_state=1)
        fe = FeatureEngineer(FeatureEngineeringConfig(select_features=False))

        result = await fe.fit_transform(X, y, "binary_classification")

        assert fe.excluded_features == ["customer_id", "row_number"]
        assert result.metadata["excluded_features"] == ["customer_id", "row_number"]
        assert "customer_id" not in fe.categorical_features
        assert "row_number" not in fe.numeric_features
        assert not any(n.startswith(("customer_id", "row_number")) for n in result.feature_names)
        assert len(result.feature_names) == 2 + 3  # tenure, monthly_charges, plan one-hot

    async def test_ordinary_columns_are_kept(self):
        """Continuous values are unique but not a row counter; a categorical
        repeats. Neither is an identifier."""
        X, y = _with_ids()
        X = X.drop(columns=["customer_id", "row_number"])
        X["sorted_unique_floats"] = np.sort(np.random.RandomState(2).uniform(0, 1, len(X)))
        # A file sorted by a real integer feature: unique and monotone, but not
        # named like an ID.
        X["sqft"] = np.arange(500, 500 + 3 * len(X), 3)
        fe = FeatureEngineer(FeatureEngineeringConfig(select_features=False))

        await fe.fit_transform(X, y, "binary_classification")

        assert fe.excluded_features == []

    @pytest.mark.parametrize(
        "name", ["id", "ID", "customerId", "row_number", "RowNumber", "order_no", "Unnamed: 0"]
    )
    def test_id_named_row_counters_are_identifiers(self, name):
        df = pd.DataFrame({name: np.arange(1, 51), "x": np.tile([1.0, 2.0], 25)})

        assert FeatureEngineer._identifier_columns(df, []) == [name]

    def test_a_text_id_with_blanks_is_still_an_identifier(self):
        """Uniqueness is measured over the filled cells: a 10%-blank ID is unique
        everywhere it has a value."""
        ids = [f"C{i:03d}" if i % 10 else None for i in range(100)]
        df = pd.DataFrame({"customer_id": ids, "all_blank": [None] * 100})

        assert FeatureEngineer._identifier_columns(df, []) == ["customer_id"]

    def test_a_unique_timestamp_is_not_a_text_identifier(self):
        """Only text is held to the uniqueness rule: a parquet upload keeps
        datetime64, and dates are #840's question, not #806's."""
        df = pd.DataFrame({"event_time": pd.date_range("2026-01-01", periods=50, freq="h")})

        assert FeatureEngineer._identifier_columns(df, []) == []

    @pytest.mark.parametrize("name", ["paid", "valid", "grid", "tenure", "sqft"])
    def test_names_that_merely_end_like_an_id_are_not(self, name):
        df = pd.DataFrame({name: np.arange(1, 51)})

        assert FeatureEngineer._identifier_columns(df, []) == []

    async def test_keep_columns_overrides_the_heuristic(self):
        X, y = _with_ids()
        fe = FeatureEngineer(
            FeatureEngineeringConfig(select_features=False, keep_columns=["row_number"])
        )

        await fe.fit_transform(X, y, "binary_classification")

        assert fe.excluded_features == ["customer_id"]
        assert "row_number" in fe.numeric_features

    async def test_transform_drops_an_excluded_column_when_it_is_supplied(self):
        X, y = _with_ids()
        fe = FeatureEngineer(FeatureEngineeringConfig(select_features=False))
        result = await fe.fit_transform(X, y, "binary_classification")

        with_ids = await fe.transform(X.head(3))
        without = await fe.transform(X.head(3).drop(columns=["customer_id", "row_number"]))

        assert list(with_ids.columns) == result.feature_names
        pd.testing.assert_frame_equal(with_ids, without)

    async def test_an_engineer_pickled_before_806_still_transforms(self):
        X, y = _with_ids()
        X = X.drop(columns=["customer_id", "row_number"])
        fe = FeatureEngineer(FeatureEngineeringConfig(select_features=False))
        await fe.fit_transform(X, y, "binary_classification")
        del fe.excluded_features  # the attribute did not exist on old pickles
        old = pickle.loads(pickle.dumps(fe))

        out = await old.transform(X.head(3))

        assert len(out.columns) == 5

    async def test_a_frame_of_only_identifiers_fails_with_a_clear_message(self):
        X, y = _with_ids()
        fe = FeatureEngineer()

        with pytest.raises(ValueError, match="identifier"):
            await fe.fit_transform(X[["customer_id", "row_number"]], y, "binary_classification")


async def test_the_engine_excludes_ids_through_its_own_split_and_honours_keep_columns():
    """#806 on the real pipeline, not a hand-shuffled frame: AutoMLEngine splits
    (and shuffles) before the engineer sees the rows, the numeric row counter is
    still caught, keep_columns reaches the engineer, and the exclusion lands under
    the metadata key train_model_task persists from."""
    from app.services.model_training.automl_engine import AutoMLEngine

    df = _churn_frame(200, seed=3)
    df.insert(0, "customer_id", [f"C{i:04d}" for i in range(len(df))])
    df.insert(1, "row_number", range(1, len(df) + 1))
    df.insert(2, "order_no", range(5000, 5000 + len(df)))
    engine = AutoMLEngine(max_models=1, cv_folds=2, random_state=0)

    result = await engine.run(
        df, "churned", FeatureEngineeringConfig(select_features=False, keep_columns=["order_no"])
    )

    assert engine.feature_engineer.excluded_features == ["customer_id", "row_number"]
    assert result.metadata["feature_engineering"]["excluded_features"] == ["customer_id", "row_number"]
    assert "order_no" in engine.feature_engineer.numeric_features


def _typed_categories_frame(n: int = 200) -> pd.DataFrame:
    """Categorical columns whose fitted categories are not all strings: a boolean
    with blanks (bools), a low-cardinality int, a low-cardinality float with blanks."""
    rng = np.random.RandomState(0)
    active = rng.choice([True, False], n).astype(object)
    active[:5] = np.nan
    level = rng.choice([1.0, 2.0, 3.0], n)
    level[5:9] = np.nan
    return pd.DataFrame(
        {
            "active": active,
            "tier": rng.choice([1, 2, 3], n),
            "level": level,
            "flag": rng.choice([True, False], n),  # bool dtype: fitted as "True"/"False"
            "plan": rng.choice(["basic", "pro"], n),
            "spend": rng.uniform(1, 100, n),
        }
    )


async def _fit_onehot(frame: pd.DataFrame) -> tuple[FeatureEngineer, FeatureEngineeringResult]:
    fe = FeatureEngineer(FeatureEngineeringConfig(encoding_method="onehot", select_features=False))
    return fe, await fe.fit_transform(frame.copy())


async def _served(fe: FeatureEngineer, records: list[dict]) -> pd.DataFrame:
    """The platform's transform of these records, which the export must reproduce."""
    rows = pd.DataFrame(records)
    out = await fe.transform(rows)
    standalone = StandaloneFeatureEngineer(pickle.loads(pickle.dumps(feature_engineer_state(fe))))
    pd.testing.assert_frame_equal(standalone.transform(rows), out, check_dtype=False)
    return out


def _block(out: pd.DataFrame, column: str) -> pd.DataFrame:
    return out[[c for c in out.columns if c.startswith(f"{column}_")]]


_RECORD = {"active": True, "tier": 1, "level": 1.0, "flag": True, "plan": "basic", "spend": 5.0}


class TestOneHotMatchesOnTheLabelKey:
    """#906: one-hot serving matched a value to a category by raw value and type, so
    the form's "1" for a category fitted as the int 1 was an all-zeros block."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "sent",
        [
            {"active": True, "tier": 1, "level": 1.0, "flag": True},
            {"active": "True", "tier": "1", "level": "1", "flag": "True"},  # what the form sends
            {"active": True, "tier": 1.0, "level": 1, "flag": "True"},
        ],
        ids=["fitted-types", "strings", "other-numeric-types"],
    )
    async def test_a_value_selects_its_category_whatever_type_it_is_sent_as(self, sent):
        fe, _ = await _fit_onehot(_typed_categories_frame())
        assert {"active", "tier", "level", "flag", "plan"} <= set(fe.categorical_features)

        out = await _served(fe, [{**_RECORD, **sent}])

        assert out.loc[0, ["active_True", "tier_1", "level_1.0", "flag_True", "plan_basic"]].tolist() == [1.0] * 5
        for column in fe.categorical_features:
            assert _block(out, column).to_numpy().sum() == 1.0

    @pytest.mark.asyncio
    async def test_every_option_the_form_offers_is_matched(self):
        from app.api.routes.model_training import _categorical_options

        fe, _ = await _fit_onehot(_typed_categories_frame())

        assert _categorical_options(fe, "level") == ["1", "2", "3"]
        for column in fe.categorical_features:
            for option in _categorical_options(fe, column):
                out = await _served(fe, [{**_RECORD, column: option}])
                assert _block(out, column).to_numpy().sum() == 1.0, (column, option)

    @pytest.mark.asyncio
    async def test_a_blank_category_is_not_offered_to_the_form(self):
        """Without an imputer a blank is a fitted category. A dropdown cannot send a
        blank, and the text "nan" is not one, so offering it offers an unseen value."""
        from app.api.routes.model_training import _categorical_options

        fe = FeatureEngineer(
            FeatureEngineeringConfig(encoding_method="onehot", select_features=False, handle_missing=False)
        )
        await fe.fit_transform(_typed_categories_frame().drop(columns=["active"]))
        assert "level_nan" in fe.transformers["encoded_columns"]  # the blank was fitted

        options = _categorical_options(fe, "level")

        assert options == ["1", "2", "3"]
        for option in options:
            out = await _served(fe, [{**_RECORD, "level": option}])
            assert _block(out, "level").to_numpy().sum() == 1.0, option

    @pytest.mark.asyncio
    async def test_a_null_in_one_record_leaves_the_others_alone(self):
        """One null makes the request's whole column `object`, which used to turn
        every other record's `true` into a value the encoder had never seen."""
        fe, _ = await _fit_onehot(_typed_categories_frame())

        out = await _served(fe, [_RECORD, {**_RECORD, "flag": None}])

        assert out.loc[0, "flag_True"] == 1.0

    @pytest.mark.asyncio
    async def test_a_value_with_no_category_is_still_all_zeros(self):
        fe, _ = await _fit_onehot(_typed_categories_frame())

        out = await _served(fe, [_RECORD, {**_RECORD, "tier": "platinum"}])

        assert out.loc[0, "tier_1"] == 1.0
        assert _block(out, "tier").loc[1].sum() == 0.0  # no such category: all zeros

    @pytest.mark.asyncio
    async def test_training_rows_encode_exactly_as_the_fitted_encoder_did(self):
        frame = _typed_categories_frame()
        fe, fitted = await _fit_onehot(frame)

        out = await fe.transform(frame)

        pd.testing.assert_frame_equal(out, fitted.X_transformed, check_dtype=False)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("text", ["1", "1.0", "01", " 1", "1e0"])
    async def test_numeric_text_selects_a_numeric_category(self, text):
        """A column fitted on numbers is matched numerically. The fitted encoder did
        this only when every categorical in the request happened to be numeric text."""
        fe, _ = await _fit_onehot(_typed_categories_frame())

        out = await _served(fe, [{**_RECORD, "tier": text, "level": text}])

        assert out.loc[0, ["tier_1", "level_1.0"]].tolist() == [1.0, 1.0]

    @pytest.mark.asyncio
    async def test_a_blank_and_the_text_that_spells_it_stay_apart(self):
        """Without an imputer a blank is a category of its own, and its label key,
        "nan", is also a string a column can hold."""
        frame = _typed_categories_frame()
        frame["plan"] = frame["plan"].astype(object)
        frame.loc[:9, "plan"] = "nan"
        frame.loc[10:19, "plan"] = np.nan
        fe = FeatureEngineer(
            FeatureEngineeringConfig(encoding_method="onehot", select_features=False, handle_missing=False)
        )
        fitted = await fe.fit_transform(frame.drop(columns=["active", "level"]))

        out = await _served(fe, frame.drop(columns=["active", "level"]).to_dict("records"))

        assert fe.transformers["encoded_columns"].count("plan_nan") == 2  # the collision is real
        np.testing.assert_array_equal(out.to_numpy(), fitted.X_transformed.to_numpy())


def _served_frame(n: int = 300) -> pd.DataFrame:
    """Text categoricals, a numeric one (`tier`), a boolean and a numeric input."""
    rng = np.random.RandomState(1)
    return pd.DataFrame(
        {
            "plan": rng.choice(["basic", "pro", "premium"], n, p=[0.6, 0.3, 0.1]),
            "region": rng.choice(["north", "south", "east"], n, p=[0.5, 0.3, 0.2]),
            "tier": rng.choice([1, 2, 3], n, p=[0.5, 0.3, 0.2]),
            "active": rng.choice([True, False], n, p=[0.7, 0.3]),
            "spend": rng.uniform(1, 100, n),
        }
    )


async def _fit_served(encoding_method: str, **config) -> FeatureEngineer:
    fe = FeatureEngineer(
        FeatureEngineeringConfig(encoding_method=encoding_method, select_features=False, **config)
    )
    await fe.fit_transform(_served_frame())
    return fe


_CLEAN = {"plan": "pro", "region": "south", "tier": 2, "active": False, "spend": 40.0}


@pytest.mark.parametrize("encoding_method", ["onehot", "label"])
class TestANullAtServingIsABlank:
    """#838: a JSON null reaches the frame as None, which SimpleImputer does not treat
    as missing, so serving never gave a null the fill a blank got at training."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("column", ["plan", "tier", "active"])
    async def test_a_null_is_served_as_the_training_fill(self, encoding_method, column):
        fe = await _fit_served(encoding_method)
        mode = _served_frame()[column].mode()[0]

        null = await _served(fe, [{**_CLEAN, column: None}])

        filled = await _served(fe, [{**_CLEAN, column: mode.item() if hasattr(mode, "item") else mode}])
        pd.testing.assert_frame_equal(null, filled, check_dtype=False)

    @pytest.mark.asyncio
    async def test_a_null_and_a_nan_are_served_alike_beside_a_clean_record(self, encoding_method):
        fe = await _fit_served(encoding_method)

        out = await _served(
            fe, [_CLEAN, {**_CLEAN, "plan": None, "region": None}, {**_CLEAN, "plan": np.nan, "region": np.nan}]
        )

        pd.testing.assert_series_equal(out.loc[1], out.loc[2], check_names=False)
        pd.testing.assert_frame_equal(out.loc[[0]], await _served(fe, [_CLEAN]), check_dtype=False)

    @pytest.mark.asyncio
    async def test_warnings_name_each_unseen_and_missing_input(self, encoding_method):
        fe = await _fit_served(encoding_method)
        records = [
            _CLEAN,
            {**_CLEAN, "plan": "enterprise"},  # never seen at fit
            {**_CLEAN, "region": None, "active": None},
            {**_CLEAN, "spend": None, "tier": 9},
            {"plan": "pro", "region": "south", "tier": "2", "active": "False", "spend": "40"},  # the form's strings
        ]

        warnings = fe.input_warnings(pd.DataFrame(records))

        assert warnings == [
            {},
            {"plan": "unseen"},
            {"region": "missing", "active": "missing"},
            {"spend": "missing", "tier": "unseen"},
            {},
        ]

    @pytest.mark.asyncio
    async def test_warnings_read_a_frame_without_changing_it_or_needing_every_column(self, encoding_method):
        fe = await _fit_served(encoding_method)
        frame = pd.DataFrame([{"plan": None, "spend": 5.0, "extra": "x"}])
        before = frame.copy()

        assert fe.input_warnings(frame) == [{"plan": "missing"}]
        pd.testing.assert_frame_equal(frame, before)

    @pytest.mark.asyncio
    async def test_an_identifier_column_is_never_flagged(self, encoding_method):
        frame = _served_frame()
        frame.insert(0, "customer_id", [f"C{i:05d}" for i in range(len(frame))])
        fe = FeatureEngineer(FeatureEngineeringConfig(encoding_method=encoding_method, select_features=False))
        await fe.fit_transform(frame)
        assert fe.excluded_features == ["customer_id"]

        assert fe.input_warnings(pd.DataFrame([{**_CLEAN, "customer_id": None}])) == [{}]


@pytest.mark.asyncio
async def test_without_encoders_only_missing_inputs_are_flagged():
    fe = await _fit_served("onehot", encode_categorical=False)

    warnings = fe.input_warnings(pd.DataFrame([{**_CLEAN, "plan": "enterprise", "spend": None}]))

    assert warnings == [{"spend": "missing"}]


@pytest.mark.asyncio
async def test_an_engineer_pickled_before_838_reports_warnings():
    """Stored engineers carry no new state: the report is read off what fit kept."""
    fe = await _fit_served("onehot")
    old = pickle.loads(pickle.dumps(fe))
    del old.__dict__["excluded_features"]  # as pickled before #806

    assert old.input_warnings(pd.DataFrame([{**_CLEAN, "plan": "enterprise"}])) == [{"plan": "unseen"}]


@pytest.mark.asyncio
async def test_a_null_number_is_served_as_a_blank_one():
    fe = await _fit_served("onehot")

    out = await _served(fe, [{**_CLEAN, "spend": None}])

    pd.testing.assert_frame_equal(out, await _served(fe, [{**_CLEAN, "spend": np.nan}]), check_dtype=False)
    assert out.loc[0, "spend"] == pytest.approx(0.0, abs=1e-9)  # the training mean, scaled
