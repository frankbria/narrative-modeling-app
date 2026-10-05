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
