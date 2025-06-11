"""
Model storage service for saving and loading ML models
"""

import pickle
import joblib
from typing import Any, Optional, Tuple
import io
from datetime import datetime, timezone
import logging
import uuid

from app.services.s3_service import S3Service
from app.models.ml_model import MLModel
from app.services.model_training.automl_engine import ModelCandidate
from app.services.model_training.feature_engineer import FeatureEngineer

logger = logging.getLogger(__name__)


class ModelStorageService:
    """Service for storing and retrieving ML models"""
    
    def __init__(self):
        self.s3_service = S3Service()
        self.models_prefix = "models/"
    
    async def save_model(
        self,
        model_candidate: ModelCandidate,
        feature_engineer: FeatureEngineer,
        user_id: str,
        dataset_id: str,
        model_metadata: dict
    ) -> MLModel:
        """
        Save a trained model and its metadata
        
        Args:
            model_candidate: Trained model candidate
            feature_engineer: Feature engineer with transformers
            user_id: User who trained the model
            dataset_id: Dataset used for training
            model_metadata: Additional metadata
            
        Returns:
            MLModel document
        """
        # Generate unique model ID
        model_id = f"model_{uuid.uuid4().hex[:12]}"
        
        # Serialize model
        model_buffer = io.BytesIO()
        joblib.dump(model_candidate.estimator, model_buffer)
        model_buffer.seek(0)
        model_size = model_buffer.getbuffer().nbytes
        
        # Upload model to S3
        model_key = f"{self.models_prefix}{user_id}/{model_id}/model.pkl"
        await self.s3_service.upload_file_obj(model_buffer, model_key)
        
        # Serialize feature engineer if it has transformers
        feature_transformer_path = None
        if feature_engineer.transformers:
            transformer_buffer = io.BytesIO()
            joblib.dump(feature_engineer, transformer_buffer)
            transformer_buffer.seek(0)
            
            transformer_key = f"{self.models_prefix}{user_id}/{model_id}/feature_transformer.pkl"
            await self.s3_service.upload_file_obj(transformer_buffer, transformer_key)
            feature_transformer_path = f"s3://{self.s3_service.bucket_name}/{transformer_key}"
        
        # Create model document
        ml_model = MLModel(
            user_id=user_id,
            dataset_id=dataset_id,
            model_id=model_id,
            name=model_metadata.get("name", f"{model_candidate.name} Model"),
            description=model_metadata.get("description"),
            problem_type=model_metadata["problem_type"],
            algorithm=model_candidate.name,
            target_column=model_metadata["target_column"],
            feature_names=model_metadata["feature_names"],
            cv_score=model_candidate.cv_score,
            test_score=model_candidate.test_score,
            metrics=model_metadata.get("metrics", {}),
            training_time=model_candidate.training_time,
            model_size=model_size,
            n_samples_train=model_metadata["n_samples_train"],
            n_features=len(model_metadata["feature_names"]),
            model_path=f"s3://{self.s3_service.bucket_name}/{model_key}",
            feature_transformer_path=feature_transformer_path,
            feature_importance=model_metadata.get("feature_importance"),
            training_config=model_metadata.get("training_config", {})
        )
        
        # Save to database
        await ml_model.insert()
        
        logger.info(f"Saved model {model_id} for user {user_id}")
        return ml_model
    
    async def load_model(self, model_id: str, user_id: str) -> Tuple[Any, Optional[FeatureEngineer]]:
        """
        Load a model and its feature transformer
        
        Args:
            model_id: Model ID to load
            user_id: User ID for authorization
            
        Returns:
            Tuple of (model, feature_engineer)
        """
        # Get model metadata
        ml_model = await MLModel.find_one(
            MLModel.model_id == model_id,
            MLModel.user_id == user_id
        )
        
        if not ml_model:
            raise ValueError(f"Model {model_id} not found for user {user_id}")
        
        # Extract S3 key from path
        model_key = ml_model.model_path.replace(f"s3://{self.s3_service.bucket_name}/", "")
        
        # Download model
        model_data = await self.s3_service.download_file_obj(model_key)
        model = joblib.load(io.BytesIO(model_data))
        
        # Load feature transformer if exists
        feature_engineer = None
        if ml_model.feature_transformer_path:
            transformer_key = ml_model.feature_transformer_path.replace(
                f"s3://{self.s3_service.bucket_name}/", ""
            )
            transformer_data = await self.s3_service.download_file_obj(transformer_key)
            feature_engineer = joblib.load(io.BytesIO(transformer_data))
        
        # Update last used timestamp
        ml_model.last_used_at = datetime.now(timezone.utc)
        await ml_model.save()
        
        return model, feature_engineer
    
    async def delete_model(self, model_id: str, user_id: str) -> bool:
        """
        Delete a model and its files
        
        Args:
            model_id: Model ID to delete
            user_id: User ID for authorization
            
        Returns:
            True if deleted successfully
        """
        # Get model metadata
        ml_model = await MLModel.find_one(
            MLModel.model_id == model_id,
            MLModel.user_id == user_id
        )
        
        if not ml_model:
            return False
        
        # Delete S3 files
        try:
            # Delete model file
            model_key = ml_model.model_path.replace(f"s3://{self.s3_service.bucket_name}/", "")
            await self.s3_service.delete_file(model_key)
            
            # Delete transformer file if exists
            if ml_model.feature_transformer_path:
                transformer_key = ml_model.feature_transformer_path.replace(
                    f"s3://{self.s3_service.bucket_name}/", ""
                )
                await self.s3_service.delete_file(transformer_key)
        except Exception as e:
            logger.error(f"Error deleting model files: {str(e)}")
        
        # Delete from database
        await ml_model.delete()
        
        logger.info(f"Deleted model {model_id} for user {user_id}")
        return True
    
    async def list_models(
        self,
        user_id: str,
        dataset_id: Optional[str] = None,
        is_active: bool = True
    ) -> list[MLModel]:
        """
        List models for a user
        
        Args:
            user_id: User ID
            dataset_id: Optional dataset filter
            is_active: Filter by active status
            
        Returns:
            List of MLModel documents
        """
        query = {"user_id": user_id, "is_active": is_active}
        if dataset_id:
            query["dataset_id"] = dataset_id
        
        models = await MLModel.find(query).sort("-created_at").to_list()
        return models