"""
Onboarding service for managing user tutorial and guidance experience
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import os

from app.schemas.onboarding import (
    OnboardingStepType,
    OnboardingStepStatus,
    OnboardingUserProgress
)
from app.models.user_data import UserData
from app.services.s3_service import S3Service
from app.services.redis_cache import cache_service


class OnboardingService:
    """Service for managing user onboarding experience"""
    
    def __init__(self):
        self.s3_service = S3Service()
        
    async def get_user_onboarding_status(self, user_id: str) -> Dict[str, Any]:
        """Get user's current onboarding status"""
        
        # Get or create user progress
        progress = await self._get_or_create_user_progress(user_id)
        
        # Calculate completion percentage
        total_steps = len(self._get_onboarding_steps_config())
        completed_count = len(progress.completed_steps)
        progress_percentage = (completed_count / total_steps) * 100 if total_steps > 0 else 0
        
        # Determine current step
        current_step_id = progress.current_step_id
        if not current_step_id and not progress.completed_steps:
            current_step_id = "welcome"
        elif not current_step_id:
            # Find next uncompleted step
            all_steps = self._get_onboarding_steps_config()
            for step in all_steps:
                if step["step_id"] not in progress.completed_steps and step["step_id"] not in progress.skipped_steps:
                    current_step_id = step["step_id"]
                    break
        
        is_complete = completed_count >= len([s for s in self._get_onboarding_steps_config() if s["is_required"]])
        
        return {
            "user_id": user_id,
            "is_onboarding_complete": is_complete,
            "current_step_id": current_step_id,
            "progress_percentage": progress_percentage,
            "total_steps": total_steps,
            "completed_steps": completed_count,
            "skipped_steps": len(progress.skipped_steps),
            "time_spent_minutes": progress.time_spent_minutes,
            "started_at": progress.started_at,
            "completed_at": progress.completed_at,
            "last_activity_at": progress.last_activity_at
        }
    
    async def get_onboarding_steps(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all onboarding steps with user's progress"""
        
        progress = await self._get_or_create_user_progress(user_id)
        steps_config = self._get_onboarding_steps_config()
        
        steps = []
        for step_config in steps_config:
            step_id = step_config["step_id"]
            
            # Determine status
            if step_id in progress.completed_steps:
                status = OnboardingStepStatus.COMPLETED
                completed_at = progress.step_completion_data.get(step_id, {}).get("completed_at")
                completion_data = progress.step_completion_data.get(step_id, {})
            elif step_id in progress.skipped_steps:
                status = OnboardingStepStatus.SKIPPED
                completed_at = None
                completion_data = None
            elif step_id == progress.current_step_id:
                status = OnboardingStepStatus.IN_PROGRESS
                completed_at = None
                completion_data = None
            else:
                status = OnboardingStepStatus.NOT_STARTED
                completed_at = None
                completion_data = None
            
            step = {
                **step_config,
                "status": status,
                "completed_at": completed_at,
                "completion_data": completion_data
            }
            steps.append(step)
        
        return steps
    
    async def get_onboarding_step(self, user_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific step"""
        
        steps = await self.get_onboarding_steps(user_id)
        return next((step for step in steps if step["step_id"] == step_id), None)
    
    async def complete_step(
        self, 
        user_id: str, 
        step_id: str, 
        completion_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Mark a step as completed and update user progress"""
        
        progress = await self._get_or_create_user_progress(user_id)
        
        # Validate step exists
        step_config = next(
            (s for s in self._get_onboarding_steps_config() if s["step_id"] == step_id), 
            None
        )
        if not step_config:
            raise ValueError(f"Invalid step ID: {step_id}")
        
        # Mark as completed
        if step_id not in progress.completed_steps:
            progress.completed_steps.append(step_id)
        
        # Remove from skipped if it was skipped before
        if step_id in progress.skipped_steps:
            progress.skipped_steps.remove(step_id)
        
        # Store completion data
        progress.step_completion_data[step_id] = {
            "completed_at": datetime.utcnow().isoformat(),
            "completion_data": completion_data or {}
        }
        
        # Update activity
        progress.last_activity_at = datetime.utcnow()
        
        # Find next step
        next_step = self._get_next_step(progress)
        progress.current_step_id = next_step
        
        # Check for achievements
        achievements = await self._check_achievements(progress)
        
        # Calculate progress
        total_steps = len(self._get_onboarding_steps_config())
        progress_percentage = (len(progress.completed_steps) / total_steps) * 100
        
        # Check if onboarding is complete
        required_steps = [s for s in self._get_onboarding_steps_config() if s["is_required"]]
        completed_required = [s for s in required_steps if s["step_id"] in progress.completed_steps]
        
        if len(completed_required) >= len(required_steps):
            progress.completed_at = datetime.utcnow()
        
        # Save progress
        await self._save_user_progress(user_id, progress)
        
        return {
            "next_step": next_step,
            "progress_percentage": progress_percentage,
            "achievements": achievements
        }
    
    async def skip_step(self, user_id: str, step_id: str) -> Dict[str, Any]:
        """Skip a step if it's skippable"""
        
        progress = await self._get_or_create_user_progress(user_id)
        
        # Validate step exists and is skippable
        step_config = next(
            (s for s in self._get_onboarding_steps_config() if s["step_id"] == step_id), 
            None
        )
        if not step_config:
            raise ValueError(f"Invalid step ID: {step_id}")
        
        if not step_config.get("is_skippable", False):
            raise ValueError(f"Step {step_id} cannot be skipped")
        
        # Mark as skipped
        if step_id not in progress.skipped_steps:
            progress.skipped_steps.append(step_id)
        
        # Remove from completed if it was completed before
        if step_id in progress.completed_steps:
            progress.completed_steps.remove(step_id)
        
        # Update activity
        progress.last_activity_at = datetime.utcnow()
        
        # Find next step
        next_step = self._get_next_step(progress)
        progress.current_step_id = next_step
        
        # Calculate progress
        total_steps = len(self._get_onboarding_steps_config())
        progress_percentage = (len(progress.completed_steps) / total_steps) * 100
        
        # Save progress
        await self._save_user_progress(user_id, progress)
        
        return {
            "next_step": next_step,
            "progress_percentage": progress_percentage
        }
    
    async def get_tutorial_progress(self, user_id: str) -> Dict[str, Any]:
        """Get detailed tutorial progress with metrics"""
        
        progress = await self._get_or_create_user_progress(user_id)
        steps = await self.get_onboarding_steps(user_id)
        
        total_steps = len(steps)
        completed_steps = len(progress.completed_steps)
        progress_percentage = (completed_steps / total_steps) * 100 if total_steps > 0 else 0
        
        # Calculate current streak
        current_streak = self._calculate_streak(progress)
        
        return {
            "user_id": user_id,
            "total_progress_percentage": progress_percentage,
            "steps_progress": steps,
            "achievements_unlocked": progress.achievements,
            "current_streak": current_streak,
            "total_time_spent_minutes": progress.time_spent_minutes,
            "features_discovered": progress.features_discovered,
            "help_articles_viewed": progress.help_articles_viewed,
            "sample_datasets_used": progress.sample_datasets_loaded
        }
    
    async def get_sample_datasets(self) -> List[Dict[str, Any]]:
        """Get available sample datasets for onboarding"""
        
        return [
            {
                "dataset_id": "customer_churn",
                "name": "Customer Churn Prediction",
                "description": "Predict which customers are likely to cancel their subscription",
                "size_mb": 2.5,
                "rows": 10000,
                "columns": 20,
                "problem_type": "binary_classification",
                "difficulty_level": "beginner",
                "tags": ["business", "classification", "customer_analysis"],
                "preview_data": [
                    {"customer_id": "C001", "tenure": 12, "monthly_charges": 50.0, "total_charges": 600.0, "churn": 0},
                    {"customer_id": "C002", "tenure": 24, "monthly_charges": 80.0, "total_charges": 1920.0, "churn": 1},
                    {"customer_id": "C003", "tenure": 6, "monthly_charges": 35.0, "total_charges": 210.0, "churn": 0},
                    {"customer_id": "C004", "tenure": 36, "monthly_charges": 90.0, "total_charges": 3240.0, "churn": 0},
                    {"customer_id": "C005", "tenure": 3, "monthly_charges": 25.0, "total_charges": 75.0, "churn": 1}
                ],
                "target_column": "churn",
                "feature_columns": ["tenure", "monthly_charges", "total_charges", "contract_type", "payment_method"],
                "learning_objectives": [
                    "Learn binary classification",
                    "Understand customer retention metrics",
                    "Practice data exploration"
                ],
                "expected_accuracy": 0.82,
                "download_url": "/api/v1/onboarding/sample-datasets/customer_churn/download",
                "documentation_url": "https://docs.narrativemodeling.ai/samples/customer-churn"
            },
            {
                "dataset_id": "house_prices",
                "name": "House Price Prediction",
                "description": "Predict house prices based on features like size, location, and amenities",
                "size_mb": 1.8,
                "rows": 5000,
                "columns": 15,
                "problem_type": "regression",
                "difficulty_level": "beginner",
                "tags": ["real_estate", "regression", "price_prediction"],
                "preview_data": [
                    {"house_id": "H001", "sqft": 1500, "bedrooms": 3, "bathrooms": 2, "price": 350000},
                    {"house_id": "H002", "sqft": 2200, "bedrooms": 4, "bathrooms": 3, "price": 480000},
                    {"house_id": "H003", "sqft": 1200, "bedrooms": 2, "bathrooms": 1, "price": 280000},
                    {"house_id": "H004", "sqft": 2800, "bedrooms": 5, "bathrooms": 4, "price": 620000},
                    {"house_id": "H005", "sqft": 1800, "bedrooms": 3, "bathrooms": 2, "price": 420000}
                ],
                "target_column": "price",
                "feature_columns": ["sqft", "bedrooms", "bathrooms", "location", "year_built"],
                "learning_objectives": [
                    "Learn regression modeling",
                    "Understand feature importance",
                    "Practice price prediction"
                ],
                "expected_accuracy": 0.85,
                "download_url": "/api/v1/onboarding/sample-datasets/house_prices/download",
                "documentation_url": "https://docs.narrativemodeling.ai/samples/house-prices"
            },
            {
                "dataset_id": "marketing_response",
                "name": "Marketing Campaign Response",
                "description": "Predict customer response to marketing campaigns",
                "size_mb": 3.2,
                "rows": 15000,
                "columns": 25,
                "problem_type": "binary_classification",
                "difficulty_level": "intermediate",
                "tags": ["marketing", "classification", "campaign_optimization"],
                "preview_data": [
                    {"customer_id": "M001", "age": 35, "income": 50000, "campaign_channel": "email", "responded": 1},
                    {"customer_id": "M002", "age": 42, "income": 75000, "campaign_channel": "phone", "responded": 0},
                    {"customer_id": "M003", "age": 28, "income": 45000, "campaign_channel": "social", "responded": 1},
                    {"customer_id": "M004", "age": 55, "income": 90000, "campaign_channel": "direct_mail", "responded": 0},
                    {"customer_id": "M005", "age": 31, "income": 60000, "campaign_channel": "email", "responded": 1}
                ],
                "target_column": "responded",
                "feature_columns": ["age", "income", "campaign_channel", "previous_purchases", "customer_segment"],
                "learning_objectives": [
                    "Learn advanced classification",
                    "Understand marketing analytics",
                    "Practice A/B testing concepts"
                ],
                "expected_accuracy": 0.78,
                "download_url": "/api/v1/onboarding/sample-datasets/marketing_response/download",
                "documentation_url": "https://docs.narrativemodeling.ai/samples/marketing-response"
            }
        ]
    
    async def load_sample_dataset(self, user_id: str, dataset_id: str) -> Dict[str, Any]:
        """Load a sample dataset for the user"""
        
        # Get dataset info
        datasets = await self.get_sample_datasets()
        dataset = next((d for d in datasets if d["dataset_id"] == dataset_id), None)
        
        if not dataset:
            raise ValueError(f"Sample dataset not found: {dataset_id}")
        
        # Upload the sample dataset file to S3 for the user
        try:
            import pandas as pd
            import os
            from app.models.user_data import UserData, SchemaField
        except ImportError as e:
            raise ValueError(f"Required dependencies not available: {e}")
        
        # Read the sample CSV file
        sample_file_path = f"/home/frankbria/projects/narrative-modeling-app/apps/backend/sample_datasets/{dataset_id}.csv"
        
        if not os.path.exists(sample_file_path):
            raise ValueError(f"Sample dataset file not found: {dataset_id}")
        
        # Read and process the dataset
        df = pd.read_csv(sample_file_path)
        
        # Create a unique filename for this user
        filename = f"sample_{dataset_id}_{user_id}_{int(datetime.utcnow().timestamp())}.csv"
        
        # Save DataFrame to temporary file and upload to S3
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            df.to_csv(temp_file.name, index=False)
            temp_file_path = temp_file.name
        
        # For now, create a mock S3 URL (in production this would upload to actual S3)
        s3_url = f"https://sample-bucket.s3.amazonaws.com/{filename}"
        
        # Infer schema
        schema_fields = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            unique_count = df[col].nunique()
            missing_count = df[col].isnull().sum()
            
            # Determine field type
            if df[col].dtype in ['int64', 'float64']:
                field_type = 'numeric'
            elif df[col].dtype == 'bool':
                field_type = 'boolean'
            elif df[col].dtype == 'datetime64[ns]':
                field_type = 'datetime'
            else:
                field_type = 'categorical' if unique_count < len(df) * 0.5 else 'text'
            
            schema_fields.append(SchemaField(
                field_name=col,
                field_type=field_type,
                data_type='nominal',
                inferred_dtype=dtype,
                unique_values=unique_count,
                missing_values=missing_count,
                example_values=df[col].dropna().head(3).tolist(),
                is_constant=unique_count == 1,
                is_high_cardinality=unique_count > len(df) * 0.8
            ))
        
        # Create UserData record
        user_data = UserData(
            user_id=user_id,
            filename=filename,
            original_filename=f"{dataset['name']}.csv",
            s3_url=s3_url,
            num_rows=len(df),
            num_columns=len(df.columns),
            data_schema=schema_fields,
            file_type="csv",
            contains_pii=False,
            is_processed=True,
            processed_at=datetime.utcnow(),
            row_count=len(df),
            columns=df.columns.tolist(),
            data_preview=df.head(5).to_dict('records')
        )
        
        await user_data.insert()
        
        # Track that user loaded this sample dataset
        progress = await self._get_or_create_user_progress(user_id)
        if dataset_id not in progress.sample_datasets_loaded:
            progress.sample_datasets_loaded.append(dataset_id)
        
        progress.features_discovered.append(f"sample_dataset_{dataset_id}")
        progress.last_activity_at = datetime.utcnow()
        
        await self._save_user_progress(user_id, progress)
        
        return {
            "dataset_id": str(user_data.id),
            "upload_id": str(user_data.id),
            "s3_url": s3_url,
            "suggested_next_steps": [
                "explore_data",
                "train_model"
            ]
        }
    
    async def reset_onboarding_progress(self, user_id: str):
        """Reset user's onboarding progress"""
        
        # Create fresh progress
        progress = OnboardingUserProgress(
            user_id=user_id,
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow()
        )
        
        await self._save_user_progress(user_id, progress)
    
    async def get_user_achievements(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's onboarding achievements"""
        
        progress = await self._get_or_create_user_progress(user_id)
        return progress.achievements
    
    async def get_contextual_help(self, user_id: str, current_step: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get contextual help tips based on current step"""
        
        help_tips = {
            "welcome": [
                {
                    "title": "Getting Started",
                    "content": "Welcome! This tutorial will guide you through building your first ML model.",
                    "type": "tip"
                },
                {
                    "title": "What You'll Learn",
                    "content": "You'll learn to upload data, explore it, train a model, and make predictions.",
                    "type": "info"
                }
            ],
            "upload_data": [
                {
                    "title": "File Formats",
                    "content": "We support CSV files. Make sure your data has column headers.",
                    "type": "tip"
                },
                {
                    "title": "Sample Data",
                    "content": "Don't have data? Try our sample datasets to get started!",
                    "type": "info"
                }
            ],
            "explore_data": [
                {
                    "title": "Data Quality",
                    "content": "Check for missing values and outliers in your data.",
                    "type": "tip"
                },
                {
                    "title": "Feature Selection",
                    "content": "Good features lead to better model performance.",
                    "type": "info"
                }
            ],
            "train_model": [
                {
                    "title": "Algorithm Selection",
                    "content": "Our AutoML will automatically choose the best algorithm for your data.",
                    "type": "tip"
                },
                {
                    "title": "Training Time",
                    "content": "Model training typically takes 2-5 minutes depending on data size.",
                    "type": "info"
                }
            ]
        }
        
        if current_step and current_step in help_tips:
            return help_tips[current_step]
        
        return help_tips.get("welcome", [])
    
    def get_help_articles(self) -> List[Dict[str, Any]]:
        """Get available help articles"""
        
        return [
            {
                "title": "Understanding Data Quality",
                "url": "/docs/data-quality",
                "category": "data_preparation",
                "estimated_read_time": "5 minutes"
            },
            {
                "title": "Choosing the Right Model Type", 
                "url": "/docs/model-types",
                "category": "machine_learning",
                "estimated_read_time": "7 minutes"
            },
            {
                "title": "Interpreting Model Results",
                "url": "/docs/model-interpretation",
                "category": "analysis",
                "estimated_read_time": "6 minutes"
            }
        ]
    
    def get_video_tutorials(self) -> List[Dict[str, Any]]:
        """Get available video tutorials"""
        
        return [
            {
                "title": "Platform Overview (3 min)",
                "url": "/videos/platform-overview",
                "duration": "3:24",
                "category": "getting_started"
            },
            {
                "title": "Your First Model (8 min)",
                "url": "/videos/first-model",
                "duration": "8:15", 
                "category": "tutorial"
            },
            {
                "title": "Advanced Features (12 min)",
                "url": "/videos/advanced-features",
                "duration": "12:30",
                "category": "advanced"
            }
        ]
    
    def _get_onboarding_steps_config(self) -> List[Dict[str, Any]]:
        """Get configuration for all onboarding steps"""
        
        return [
            {
                "step_id": "welcome",
                "title": "Welcome to Narrative Modeling",
                "description": "Learn about the platform and what you can accomplish",
                "step_type": OnboardingStepType.WELCOME,
                "order": 1,
                "is_required": True,
                "is_skippable": False,
                "estimated_duration": "2 minutes",
                "completion_criteria": [
                    "View welcome video",
                    "Read platform overview"
                ],
                "instructions": [
                    "Watch the welcome video to understand the platform",
                    "Review the key features and capabilities",
                    "Click 'Get Started' when ready to proceed"
                ],
                "help_text": "This step introduces you to the platform's core concepts.",
                "video_url": "/videos/welcome-intro"
            },
            {
                "step_id": "upload_data",
                "title": "Upload Your First Dataset",
                "description": "Learn how to upload and validate your data",
                "step_type": OnboardingStepType.UPLOAD_DATA,
                "order": 2,
                "is_required": True,
                "is_skippable": False,
                "estimated_duration": "5 minutes",
                "completion_criteria": [
                    "Successfully upload a CSV file",
                    "Pass data validation checks"
                ],
                "instructions": [
                    "Choose a CSV file or select a sample dataset",
                    "Upload the file using the upload interface",
                    "Review the data validation results",
                    "Confirm your data looks correct"
                ],
                "help_text": "We'll help you upload data and check for any quality issues.",
                "code_examples": [
                    {
                        "title": "Sample CSV Format",
                        "code": "customer_id,age,income,churn\nC001,25,50000,0\nC002,35,75000,1"
                    }
                ]
            },
            {
                "step_id": "explore_data",
                "title": "Explore Your Data",
                "description": "Use our data analysis tools to understand your dataset",
                "step_type": OnboardingStepType.EXPLORE_DATA,
                "order": 3,
                "is_required": True,
                "is_skippable": False,
                "estimated_duration": "8 minutes",
                "completion_criteria": [
                    "View data summary statistics",
                    "Generate at least one visualization",
                    "Review data quality report"
                ],
                "instructions": [
                    "Review the automatic data summary",
                    "Create visualizations to understand your data",
                    "Check the data quality assessment",
                    "Identify your target column for prediction"
                ],
                "help_text": "Data exploration helps you understand patterns and prepare for modeling."
            },
            {
                "step_id": "train_model",
                "title": "Train Your First Model",
                "description": "Use AutoML to automatically train a machine learning model",
                "step_type": OnboardingStepType.TRAIN_MODEL,
                "order": 4,
                "is_required": True,
                "is_skippable": False,
                "estimated_duration": "10 minutes",
                "completion_criteria": [
                    "Select target column",
                    "Start model training",
                    "Wait for training completion",
                    "Review model performance"
                ],
                "instructions": [
                    "Choose your target column (what you want to predict)",
                    "Select the problem type (classification or regression)",
                    "Start the AutoML training process",
                    "Review the model's performance metrics"
                ],
                "help_text": "Our AutoML will automatically find the best algorithm for your data."
            },
            {
                "step_id": "make_predictions",
                "title": "Make Predictions",
                "description": "Use your trained model to make predictions on new data",
                "step_type": OnboardingStepType.MAKE_PREDICTIONS,
                "order": 5,
                "is_required": True,
                "is_skippable": False,
                "estimated_duration": "5 minutes",
                "completion_criteria": [
                    "Make at least one prediction",
                    "Understand prediction confidence"
                ],
                "instructions": [
                    "Enter sample data for prediction",
                    "Review the prediction results",
                    "Understand confidence scores",
                    "Try different input values"
                ],
                "help_text": "This is where your model becomes useful - making predictions on new data!"
            },
            {
                "step_id": "export_model",
                "title": "Export and Deploy",
                "description": "Learn how to export your model for production use",
                "step_type": OnboardingStepType.EXPORT_MODEL,
                "order": 6,
                "is_required": False,
                "is_skippable": True,
                "estimated_duration": "7 minutes",
                "completion_criteria": [
                    "Download model in at least one format",
                    "Review deployment options"
                ],
                "instructions": [
                    "Choose an export format (Python, Docker, ONNX)",
                    "Download your model",
                    "Review the deployment documentation",
                    "Consider integration options"
                ],
                "help_text": "Export your model to use it in your own applications and systems."
            },
            {
                "step_id": "completion",
                "title": "Congratulations!",
                "description": "You've completed the onboarding tutorial",
                "step_type": OnboardingStepType.COMPLETION,
                "order": 7,
                "is_required": False,
                "is_skippable": False,
                "estimated_duration": "3 minutes",
                "completion_criteria": [
                    "Review what you've learned",
                    "Explore next steps"
                ],
                "instructions": [
                    "Celebrate your success!",
                    "Review what you've accomplished",
                    "Explore advanced features",
                    "Join our community"
                ],
                "help_text": "You're now ready to build amazing ML models!"
            }
        ]
    
    def _get_next_step(self, progress: OnboardingUserProgress) -> Optional[str]:
        """Find the next uncompleted step"""
        
        all_steps = self._get_onboarding_steps_config()
        
        for step in all_steps:
            step_id = step["step_id"]
            if step_id not in progress.completed_steps and step_id not in progress.skipped_steps:
                return step_id
        
        return None
    
    async def _check_achievements(self, progress: OnboardingUserProgress) -> List[Dict[str, Any]]:
        """Check for new achievements based on progress"""
        
        new_achievements = []
        
        # First upload achievement
        if ("upload_data" in progress.completed_steps and 
            not any(a.get("id") == "first_upload" for a in progress.achievements)):
            new_achievements.append({
                "id": "first_upload",
                "title": "Data Explorer",
                "description": "Uploaded your first dataset",
                "type": "badge",
                "points": 10,
                "earned_at": datetime.utcnow().isoformat()
            })
        
        # First model achievement  
        if ("train_model" in progress.completed_steps and
            not any(a.get("id") == "first_model" for a in progress.achievements)):
            new_achievements.append({
                "id": "first_model",
                "title": "Model Builder",
                "description": "Trained your first ML model",
                "type": "badge", 
                "points": 25,
                "earned_at": datetime.utcnow().isoformat()
            })
        
        # Completion achievement
        required_steps = [s for s in self._get_onboarding_steps_config() if s["is_required"]]
        completed_required = [s for s in required_steps if s["step_id"] in progress.completed_steps]
        
        if (len(completed_required) >= len(required_steps) and
            not any(a.get("id") == "onboarding_complete" for a in progress.achievements)):
            new_achievements.append({
                "id": "onboarding_complete",
                "title": "Tutorial Master",
                "description": "Completed the full onboarding experience",
                "type": "milestone",
                "points": 50,
                "earned_at": datetime.utcnow().isoformat()
            })
        
        # Add new achievements to progress
        progress.achievements.extend(new_achievements)
        
        return new_achievements
    
    def _calculate_streak(self, progress: OnboardingUserProgress) -> int:
        """Calculate user's current learning streak"""
        
        # Simple implementation - count consecutive days with activity
        # In a real implementation, you'd track daily activity
        
        if not progress.completed_steps:
            return 0
        
        # For now, return number of completed steps as a proxy
        return len(progress.completed_steps)
    
    async def _get_or_create_user_progress(self, user_id: str) -> OnboardingUserProgress:
        """Get existing user progress or create new one with caching"""
        
        # Try to get from cache first
        cached_progress = await cache_service.get_user_progress(user_id)
        if cached_progress:
            return OnboardingUserProgress(**cached_progress)
        
        # Try to load from database (user_data collection)
        user_data = await UserData.find_one({"user_id": user_id})
        
        if user_data and hasattr(user_data, 'onboarding_progress') and user_data.onboarding_progress:
            # Convert stored data to OnboardingUserProgress
            progress_data = user_data.onboarding_progress
            progress = OnboardingUserProgress(**progress_data)
        else:
            # Create new progress
            progress = OnboardingUserProgress(
                user_id=user_id,
                started_at=datetime.utcnow(),
                last_activity_at=datetime.utcnow()
            )
        
        # Cache the progress
        await cache_service.cache_user_progress(user_id, progress.dict())
        
        return progress
    
    async def _save_user_progress(self, user_id: str, progress: OnboardingUserProgress):
        """Save user progress to database and cache"""
        
        # Convert to dict for storage
        progress_dict = progress.dict()
        
        # Update cache first for fast access
        await cache_service.cache_user_progress(user_id, progress_dict)
        
        # Update or create user_data document
        user_data = await UserData.find_one({"user_id": user_id})
        
        if user_data:
            user_data.onboarding_progress = progress_dict
            await user_data.save()
        else:
            # Create new user_data document
            user_data = UserData(
                user_id=user_id,
                onboarding_progress=progress_dict
            )
            await user_data.insert()