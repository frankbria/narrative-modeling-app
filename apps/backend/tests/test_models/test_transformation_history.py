"""
Tests for TransformationConfig history functionality - Unit tests only (no database required).

Tests cover:
- current_position field defaults
- can_undo() method
- can_redo() method
- get_current_state() method
- add_transformation_step() with branching (truncates forward history)
"""

from app.models.transformation import (
    TransformationConfig
)


class TestTransformationConfigHistory:
    """Tests for TransformationConfig history tracking functionality."""

    def test_current_position_defaults_to_negative_one(self):
        """Test that current_position defaults to -1 (no transformations applied)."""
        config = TransformationConfig.model_construct(
            user_id="user1",
            dataset_id="ds1",
            config_id="config1"
        )

        assert config.current_position == -1

    def test_can_undo_returns_false_when_at_beginning(self):
        """Test can_undo() returns False when current_position is -1 or 0."""
        config = TransformationConfig.model_construct(
            user_id="user1",
            dataset_id="ds1",
            config_id="config1",
            transformation_steps=[],
            total_transformations=0
        )

        # At -1 (no transformations)
        assert config.can_undo() is False

        # Add one step and set position to 0
        config.add_transformation_step("encode", column="col1", parameters={})
        config.current_position = 0
        assert config.can_undo() is False

    def test_can_undo_returns_true_when_position_greater_than_zero(self):
        """Test can_undo() returns True when current_position > 0."""
        config = TransformationConfig.model_construct(
            user_id="user1",
            dataset_id="ds1",
            config_id="config1",
            transformation_steps=[],
            total_transformations=0
        )

        # Add two steps
        config.add_transformation_step("encode", column="col1", parameters={})
        config.add_transformation_step("scale", column="col2", parameters={})
        config.current_position = 1

        assert config.can_undo() is True

    def test_can_redo_returns_false_when_at_end(self):
        """Test can_redo() returns False when current_position is at the end of history."""
        config = TransformationConfig.model_construct(
            user_id="user1",
            dataset_id="ds1",
            config_id="config1",
            transformation_steps=[],
            total_transformations=0
        )

        # No transformations
        assert config.can_redo() is False

        # Add steps and set position to last step
        config.add_transformation_step("encode", column="col1", parameters={})
        config.add_transformation_step("scale", column="col2", parameters={})
        config.current_position = 1  # At the end (0-indexed, so position 1 = 2nd step)

        assert config.can_redo() is False

    def test_can_redo_returns_true_when_not_at_end(self):
        """Test can_redo() returns True when current_position < len(transformation_steps) - 1."""
        config = TransformationConfig.model_construct(
            user_id="user1",
            dataset_id="ds1",
            config_id="config1",
            transformation_steps=[],
            total_transformations=0
        )

        # Add three steps
        config.add_transformation_step("encode", column="col1", parameters={})
        config.add_transformation_step("scale", column="col2", parameters={})
        config.add_transformation_step("impute", column="col3", parameters={})
        config.current_position = 1  # Not at the end (can move forward to position 2)

        assert config.can_redo() is True

    def test_get_current_state_returns_correct_metadata(self):
        """Test get_current_state() returns correct position and navigation state."""
        config = TransformationConfig.model_construct(
            user_id="user1",
            dataset_id="ds1",
            config_id="config1",
            transformation_steps=[],
            total_transformations=0
        )

        # Add three steps
        config.add_transformation_step("encode", column="col1", parameters={})
        config.add_transformation_step("scale", column="col2", parameters={})
        config.add_transformation_step("impute", column="col3", parameters={})
        config.current_position = 1

        state = config.get_current_state()

        assert state["current_position"] == 1
        assert state["total_steps"] == 3
        assert state["can_undo"] is True
        assert state["can_redo"] is True

    def test_get_current_state_at_beginning(self):
        """Test get_current_state() when at the beginning of history."""
        config = TransformationConfig.model_construct(
            user_id="user1",
            dataset_id="ds1",
            config_id="config1",
            transformation_steps=[],
            total_transformations=0
        )

        state = config.get_current_state()

        assert state["current_position"] == -1
        assert state["total_steps"] == 0
        assert state["can_undo"] is False
        assert state["can_redo"] is False

    def test_get_current_state_at_end(self):
        """Test get_current_state() when at the end of history."""
        config = TransformationConfig.model_construct(
            user_id="user1",
            dataset_id="ds1",
            config_id="config1",
            transformation_steps=[],
            total_transformations=0
        )

        # Add two steps
        config.add_transformation_step("encode", column="col1", parameters={})
        config.add_transformation_step("scale", column="col2", parameters={})
        config.current_position = 1

        state = config.get_current_state()

        assert state["current_position"] == 1
        assert state["total_steps"] == 2
        assert state["can_undo"] is True
        assert state["can_redo"] is False

    def test_add_transformation_step_truncates_forward_history(self):
        """Test that add_transformation_step() truncates forward history when branching."""
        config = TransformationConfig.model_construct(
            user_id="user1",
            dataset_id="ds1",
            config_id="config1",
            transformation_steps=[],
            total_transformations=0
        )

        # Add three steps
        config.add_transformation_step("encode", column="col1", parameters={})
        config.add_transformation_step("scale", column="col2", parameters={})
        config.add_transformation_step("impute", column="col3", parameters={})

        # Simulate undo: move position back to 1 (pointing at 2nd step)
        config.current_position = 1

        # Add a new step - this should truncate step at position 2
        config.add_transformation_step("normalize", column="col4", parameters={})

        # Should now have 3 steps total (0: encode, 1: scale, 2: normalize)
        assert len(config.transformation_steps) == 3
        assert config.transformation_steps[2].transformation_type == "normalize"
        assert config.current_position == 2  # Position should be updated to new step

    def test_add_transformation_step_does_not_truncate_when_at_end(self):
        """Test that add_transformation_step() doesn't truncate when at the end."""
        config = TransformationConfig.model_construct(
            user_id="user1",
            dataset_id="ds1",
            config_id="config1",
            transformation_steps=[],
            total_transformations=0
        )

        # Add two steps
        config.add_transformation_step("encode", column="col1", parameters={})
        config.add_transformation_step("scale", column="col2", parameters={})
        config.current_position = 1  # At the end

        # Add a new step
        config.add_transformation_step("impute", column="col3", parameters={})

        # Should have all 3 steps
        assert len(config.transformation_steps) == 3
        assert config.current_position == 2

    def test_add_transformation_step_with_no_history(self):
        """Test that add_transformation_step() works correctly with no existing history."""
        config = TransformationConfig.model_construct(
            user_id="user1",
            dataset_id="ds1",
            config_id="config1",
            transformation_steps=[],
            total_transformations=0
        )

        # current_position is -1 (no history)
        assert config.current_position == -1

        # Add first step
        config.add_transformation_step("encode", column="col1", parameters={})

        # Should have 1 step, position should be 0
        assert len(config.transformation_steps) == 1
        assert config.current_position == 0

    def test_branching_scenario_complex(self):
        """Test complex branching scenario with multiple undo/redo/apply operations."""
        config = TransformationConfig.model_construct(
            user_id="user1",
            dataset_id="ds1",
            config_id="config1",
            transformation_steps=[],
            total_transformations=0
        )

        # Build initial history: encode -> scale -> impute -> normalize
        config.add_transformation_step("encode", column="col1", parameters={})
        config.add_transformation_step("scale", column="col2", parameters={})
        config.add_transformation_step("impute", column="col3", parameters={})
        config.add_transformation_step("normalize", column="col4", parameters={})

        assert len(config.transformation_steps) == 4
        assert config.current_position == 3

        # Undo twice (back to position 1)
        config.current_position = 1

        # Branch: add new transformation
        config.add_transformation_step("fill_missing", column="col5", parameters={})

        # History should be: encode -> scale -> fill_missing
        assert len(config.transformation_steps) == 3
        assert config.transformation_steps[0].transformation_type == "encode"
        assert config.transformation_steps[1].transformation_type == "scale"
        assert config.transformation_steps[2].transformation_type == "fill_missing"
        assert config.current_position == 2
