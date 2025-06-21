"""
Tests for onboarding API routes
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.auth.nextauth_auth import get_current_user_id


@pytest.fixture
def client():
    """Create test client"""
    # Override auth dependency for testing
    def fake_get_current_user_id():
        return "test_user_123"
    
    app.dependency_overrides[get_current_user_id] = fake_get_current_user_id
    
    # Use authorized_client fixture instead
    
    yield client
    
    # Clean up
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def mock_onboarding_status():
    """Mock onboarding status"""
    return {
        "user_id": "test_user_123",
        "is_onboarding_complete": False,
        "current_step_id": "upload_data",
        "progress_percentage": 25.0,
        "total_steps": 7,
        "completed_steps": 2,
        "skipped_steps": 0,
        "time_spent_minutes": 15,
        "started_at": "2024-01-01T12:00:00Z",
        "completed_at": None,
        "last_activity_at": "2024-01-01T12:15:00Z"
    }


@pytest.fixture
def mock_onboarding_steps():
    """Mock onboarding steps"""
    return [
        {
            "step_id": "welcome",
            "title": "Welcome to Narrative Modeling",
            "description": "Learn about the platform",
            "step_type": "welcome",
            "status": "completed",
            "order": 1,
            "is_required": True,
            "is_skippable": False,
            "estimated_duration": "2 minutes",
            "completion_criteria": ["View welcome video"],
            "instructions": ["Watch the video", "Click continue"],
            "help_text": "This introduces the platform",
            "completed_at": "2024-01-01T12:05:00Z"
        },
        {
            "step_id": "upload_data",
            "title": "Upload Your First Dataset",
            "description": "Learn how to upload data",
            "step_type": "upload_data",
            "status": "in_progress",
            "order": 2,
            "is_required": True,
            "is_skippable": False,
            "estimated_duration": "5 minutes",
            "completion_criteria": ["Upload a CSV file"],
            "instructions": ["Choose a file", "Upload it"],
            "help_text": "Upload CSV files with headers"
        }
    ]


@pytest.fixture
def mock_sample_datasets():
    """Mock sample datasets"""
    return [
        {
            "dataset_id": "customer_churn",
            "name": "Customer Churn Prediction",
            "description": "Predict customer churn",
            "size_mb": 2.5,
            "rows": 10000,
            "columns": 20,
            "problem_type": "binary_classification",
            "difficulty_level": "beginner",
            "tags": ["business", "classification"],
            "preview_data": [
                {"customer_id": "C001", "tenure": 12, "churn": 0}
            ],
            "target_column": "churn",
            "feature_columns": ["tenure", "monthly_charges"],
            "learning_objectives": ["Learn binary classification"],
            "expected_accuracy": 0.82,
            "download_url": "/api/v1/sample-datasets/customer_churn/download",
            "documentation_url": "https://docs.example.com/churn"
        }
    ]


class TestOnboardingRoutes:
    """Test cases for onboarding API routes"""
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_get_onboarding_status_success(
        self, 
        mock_service_class, 
        authorized_client, 
        mock_onboarding_status
    ):
        """Test successful onboarding status retrieval"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.get_user_onboarding_status = AsyncMock(return_value=mock_onboarding_status)
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.get("/api/onboarding/status")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["user_id"] == "test_user_123"
        assert data["is_onboarding_complete"] is False
        assert data["current_step_id"] == "upload_data"
        assert data["progress_percentage"] == 25.0
        assert data["total_steps"] == 7
        assert data["completed_steps"] == 2
        
        # Verify service was called
        mock_service.get_user_onboarding_status.assert_called_once_with("test_user_123")
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_get_onboarding_steps_success(
        self, 
        mock_service_class, 
        authorized_client, 
        mock_onboarding_steps
    ):
        """Test successful onboarding steps retrieval"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.get_onboarding_steps = AsyncMock(return_value=mock_onboarding_steps)
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.get("/api/onboarding/steps")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 2
        assert data[0]["step_id"] == "welcome"
        assert data[0]["status"] == "completed"
        assert data[1]["step_id"] == "upload_data"
        assert data[1]["status"] == "in_progress"
        
        # Verify service was called
        mock_service.get_onboarding_steps.assert_called_once_with("test_user_123")
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_get_onboarding_step_success(
        self, 
        mock_service_class, 
        authorized_client, 
        mock_onboarding_steps
    ):
        """Test successful single step retrieval"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.get_onboarding_step = AsyncMock(return_value=mock_onboarding_steps[0])
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.get("/api/onboarding/steps/welcome")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["step_id"] == "welcome"
        assert data["title"] == "Welcome to Narrative Modeling"
        assert data["status"] == "completed"
        
        # Verify service was called
        mock_service.get_onboarding_step.assert_called_once_with("test_user_123", "welcome")
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_get_onboarding_step_not_found(self, mock_service_class, authorized_client):
        """Test step not found"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.get_onboarding_step = AsyncMock(return_value=None)
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.get("/api/onboarding/steps/nonexistent")
        
        # Verify response
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_complete_onboarding_step_success(self, mock_service_class, authorized_client):
        """Test successful step completion"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.complete_step = AsyncMock(return_value={
            "next_step": "explore_data",
            "progress_percentage": 50.0,
            "achievements": [{"title": "First Upload", "points": 10}]
        })
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.post(
            "/api/onboarding/steps/upload_data/complete",
            json={"completion_data": {"file_uploaded": True}}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["next_step"] == "explore_data"
        assert data["progress_percentage"] == 50.0
        assert len(data["achievements"]) == 1
        
        # Verify service was called
        mock_service.complete_step.assert_called_once_with(
            user_id="test_user_123",
            step_id="upload_data",
            completion_data={"file_uploaded": True}
        )
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_complete_onboarding_step_error(self, mock_service_class, authorized_client):
        """Test step completion error"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.complete_step = AsyncMock(side_effect=ValueError("Invalid step"))
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.post(
            "/api/onboarding/steps/invalid/complete",
            json={"completion_data": {}}
        )
        
        # Verify response
        assert response.status_code == 400
        assert "Invalid step" in response.json()["detail"]
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_skip_onboarding_step_success(self, mock_service_class, authorized_client):
        """Test successful step skipping"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.skip_step = AsyncMock(return_value={
            "next_step": "train_model",
            "progress_percentage": 75.0
        })
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.post("/api/onboarding/skip-step/explore_data")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["next_step"] == "train_model"
        assert data["progress_percentage"] == 75.0
        
        # Verify service was called
        mock_service.skip_step.assert_called_once_with("test_user_123", "explore_data")
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_skip_onboarding_step_not_skippable(self, mock_service_class, authorized_client):
        """Test skipping non-skippable step"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.skip_step = AsyncMock(side_effect=ValueError("Step cannot be skipped"))
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.post("/api/onboarding/skip-step/welcome")
        
        # Verify response
        assert response.status_code == 400
        assert "cannot be skipped" in response.json()["detail"]
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_get_tutorial_progress_success(self, mock_service_class, authorized_client):
        """Test tutorial progress retrieval"""
        
        mock_progress = {
            "user_id": "test_user_123",
            "total_progress_percentage": 60.0,
            "steps_progress": [],
            "achievements_unlocked": [],
            "current_streak": 5,
            "total_time_spent_minutes": 30,
            "features_discovered": ["upload", "explore"],
            "help_articles_viewed": ["data-quality"],
            "sample_datasets_used": ["customer_churn"]
        }
        
        # Setup mock
        mock_service = Mock()
        mock_service.get_tutorial_progress = AsyncMock(return_value=mock_progress)
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.get("/api/onboarding/tutorial-progress")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["user_id"] == "test_user_123"
        assert data["total_progress_percentage"] == 60.0
        assert data["current_streak"] == 5
        assert "upload" in data["features_discovered"]
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_get_sample_datasets_success(
        self, 
        mock_service_class, 
        authorized_client, 
        mock_sample_datasets
    ):
        """Test sample datasets retrieval"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.get_sample_datasets = AsyncMock(return_value=mock_sample_datasets)
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.get("/api/onboarding/sample-datasets")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1
        assert data[0]["dataset_id"] == "customer_churn"
        assert data[0]["name"] == "Customer Churn Prediction"
        assert data[0]["problem_type"] == "binary_classification"
        assert data[0]["difficulty_level"] == "beginner"
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_load_sample_dataset_success(self, mock_service_class, authorized_client):
        """Test successful sample dataset loading"""
        
        mock_result = {
            "dataset_id": "dataset_123",
            "upload_id": "upload_456",
            "s3_url": "https://s3.amazonaws.com/bucket/file.csv",
            "suggested_next_steps": ["explore_data", "train_model"]
        }
        
        # Setup mock
        mock_service = Mock()
        mock_service.load_sample_dataset = AsyncMock(return_value=mock_result)
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.post("/api/onboarding/sample-datasets/customer_churn/load")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["dataset_id"] == "dataset_123"
        assert data["upload_id"] == "upload_456"
        assert "explore_data" in data["suggested_next_steps"]
        
        # Verify service was called
        mock_service.load_sample_dataset.assert_called_once_with(
            "test_user_123", 
            "customer_churn"
        )
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_load_sample_dataset_not_found(self, mock_service_class, authorized_client):
        """Test loading non-existent sample dataset"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.load_sample_dataset = AsyncMock(
            side_effect=ValueError("Sample dataset not found")
        )
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.post("/api/onboarding/sample-datasets/nonexistent/load")
        
        # Verify response
        assert response.status_code == 400
        assert "not found" in response.json()["detail"]
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_reset_onboarding_success(self, mock_service_class, authorized_client):
        """Test successful onboarding reset"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.reset_onboarding_progress = AsyncMock()
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.post("/api/onboarding/reset")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "reset successfully" in data["message"]
        
        # Verify service was called
        mock_service.reset_onboarding_progress.assert_called_once_with("test_user_123")
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_get_user_achievements_success(self, mock_service_class, authorized_client):
        """Test user achievements retrieval"""
        
        mock_achievements = [
            {
                "id": "first_upload",
                "title": "Data Explorer",
                "description": "Uploaded first dataset",
                "type": "badge",
                "points": 10,
                "earned_at": "2024-01-01T12:00:00Z"
            },
            {
                "id": "first_model", 
                "title": "Model Builder",
                "description": "Trained first model",
                "type": "milestone",
                "points": 25,
                "earned_at": "2024-01-01T12:30:00Z"
            }
        ]
        
        # Setup mock
        mock_service = Mock()
        mock_service.get_user_achievements = AsyncMock(return_value=mock_achievements)
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.get("/api/onboarding/achievements")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["achievements"]) == 2
        assert data["total_points"] == 35
        assert len(data["badges_earned"]) == 1
        assert len(data["milestones_reached"]) == 1
        
        # Check specific achievements
        badges = data["badges_earned"]
        assert badges[0]["title"] == "Data Explorer"
        
        milestones = data["milestones_reached"]
        assert milestones[0]["title"] == "Model Builder"
    
    @patch('app.api.routes.onboarding.OnboardingService')
    def test_get_contextual_help_success(self, mock_service_class, authorized_client):
        """Test contextual help retrieval"""
        
        mock_tips = [
            {
                "title": "File Formats",
                "content": "We support CSV files with headers",
                "type": "tip"
            }
        ]
        
        mock_help_articles = [
            {
                "title": "Understanding Data Quality",
                "url": "/docs/data-quality",
                "category": "data_preparation"
            }
        ]
        
        mock_video_tutorials = [
            {
                "title": "Platform Overview",
                "url": "/videos/overview",
                "duration": "3:24"
            }
        ]
        
        # Setup mock
        mock_service = Mock()
        mock_service.get_contextual_help = AsyncMock(return_value=mock_tips)
        mock_service.get_help_articles.return_value = mock_help_articles
        mock_service.get_video_tutorials.return_value = mock_video_tutorials
        mock_service_class.return_value = mock_service
        
        # Make request
        response = authorized_client.get("/api/onboarding/help-tips?current_step=upload_data")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["tips"]) == 1
        assert data["tips"][0]["title"] == "File Formats"
        assert len(data["help_articles"]) == 1
        assert len(data["video_tutorials"]) == 1
        assert "support_contact" in data
        
        # Verify service was called
        mock_service.get_contextual_help.assert_called_once_with(
            "test_user_123", 
            "upload_data"
        )