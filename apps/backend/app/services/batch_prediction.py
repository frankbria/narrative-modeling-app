"""
Batch prediction service for processing large datasets
"""
import asyncio
import json
import pandas as pd
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
from datetime import datetime
import tempfile
import os
from io import StringIO, BytesIO
import boto3
from botocore.exceptions import NoCredentialsError

from app.models.batch_job import BatchJob, JobStatus, JobType, BatchPredictionConfig
from app.models.ml_model import MLModel
from app.services.model_storage import ModelStorageService
from app.services.s3_service import S3Service
from beanie import PydanticObjectId


class BatchPredictionService:
    """Service for managing batch prediction jobs"""
    
    def __init__(self):
        self.s3_service = S3Service()
        self.model_storage = ModelStorageService()
    
    async def create_batch_prediction_job(
        self,
        user_id: str,
        model_id: str,
        input_data: Any,  # Can be file path, DataFrame, or list of dicts
        output_format: str = "csv",
        include_probabilities: bool = True,
        chunk_size: int = 1000,
        priority: int = 0
    ) -> BatchJob:
        """Create a new batch prediction job"""
        
        # Validate model exists and user has access
        model = await MLModel.find_one({
            "model_id": model_id,
            "user_id": user_id,
            "is_active": True
        })
        
        if not model:
            raise ValueError("Model not found or not accessible")
        
        # Prepare input data and upload to S3 if needed
        input_path, total_records = await self._prepare_input_data(
            input_data, user_id, model_id
        )
        
        # Create job configuration
        config = BatchPredictionConfig(
            model_id=model_id,
            output_format=output_format,
            include_probabilities=include_probabilities,
            chunk_size=chunk_size
        ).dict()
        
        # Create job
        job = BatchJob(
            job_id=f"batch_{PydanticObjectId()}",
            job_type=JobType.BATCH_PREDICTION,
            user_id=user_id,
            config=config,
            input_path=input_path,
            priority=priority
        )
        
        # Initialize progress
        job.progress.total_records = total_records
        job.progress.total_chunks = (total_records + chunk_size - 1) // chunk_size
        
        await job.create()
        
        # Start processing asynchronously
        asyncio.create_task(self._process_batch_job(job))
        
        return job
    
    async def _prepare_input_data(
        self,
        input_data: Any,
        user_id: str,
        model_id: str
    ) -> Tuple[str, int]:
        """Prepare and upload input data to S3"""
        
        # Generate unique S3 path
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        s3_key = f"batch-jobs/{user_id}/{model_id}/{timestamp}/input.csv"
        
        if isinstance(input_data, str):
            # Assume it's a file path
            if not os.path.exists(input_data):
                raise ValueError("Input file not found")
            
            # Count records
            df = pd.read_csv(input_data)
            total_records = len(df)
            
            # Upload to S3
            await self.s3_service.upload_file(input_data, s3_key)
            
        elif isinstance(input_data, pd.DataFrame):
            # Convert DataFrame to CSV and upload
            csv_buffer = StringIO()
            input_data.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue().encode('utf-8')
            
            total_records = len(input_data)
            
            # Upload to S3
            await self.s3_service.upload_file_content(csv_content, s3_key)
            
        elif isinstance(input_data, list):
            # Convert list to DataFrame then CSV
            df = pd.DataFrame(input_data)
            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue().encode('utf-8')
            
            total_records = len(input_data)
            
            # Upload to S3
            await self.s3_service.upload_file_content(csv_content, s3_key)
            
        else:
            raise ValueError("Unsupported input data type")
        
        return s3_key, total_records
    
    async def _process_batch_job(self, job: BatchJob) -> None:
        """Process a batch prediction job asynchronously"""
        
        try:
            # Mark job as started
            job.mark_started()
            await job.save()
            
            # Load model
            config = BatchPredictionConfig(**job.config)
            model = await MLModel.find_one({"model_id": config.model_id})
            
            if not model:
                raise ValueError("Model not found")
            
            # Load model artifacts
            model_artifacts = await self.model_storage.load_model(model.model_path)
            trained_model = model_artifacts["model"]
            feature_engineer = model_artifacts.get("feature_engineer")
            
            # Process data in chunks
            predictions = []
            chunk_num = 0
            
            async for chunk_df in self._read_data_chunks(job.input_path, config.chunk_size):
                chunk_num += 1
                
                try:
                    # Make predictions for chunk
                    chunk_predictions = await self._predict_chunk(
                        chunk_df,
                        trained_model,
                        feature_engineer,
                        model,
                        config
                    )
                    
                    predictions.extend(chunk_predictions)
                    
                    # Update progress
                    job.update_progress(
                        processed_records=len(predictions),
                        success_count=len([p for p in chunk_predictions if p.get('error') is None]),
                        error_count=len([p for p in chunk_predictions if p.get('error') is not None]),
                        current_chunk=chunk_num
                    )
                    
                    await job.save()
                    
                except Exception as e:
                    # Handle chunk processing error
                    error_predictions = [
                        {"error": str(e), "row_index": i} 
                        for i in range(len(chunk_df))
                    ]
                    predictions.extend(error_predictions)
                    
                    job.update_progress(
                        processed_records=len(predictions),
                        error_count=job.progress.error_count + len(error_predictions),
                        current_chunk=chunk_num
                    )
                    await job.save()
            
            # Save results to S3
            output_path = await self._save_results(job, predictions, config)
            job.output_path = output_path
            
            # Mark job as completed
            job.mark_completed({
                "output_path": output_path,
                "total_predictions": len(predictions),
                "success_rate": job.progress.success_rate
            })
            
        except Exception as e:
            job.mark_failed(str(e))
        
        finally:
            await job.save()
    
    async def _read_data_chunks(
        self,
        s3_path: str,
        chunk_size: int
    ) -> AsyncGenerator[pd.DataFrame, None]:
        """Read data from S3 in chunks"""
        
        # Download file from S3
        content = await self.s3_service.download_file_content(s3_path)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.csv') as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Read in chunks
            for chunk in pd.read_csv(temp_file_path, chunksize=chunk_size):
                yield chunk
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
    
    async def _predict_chunk(
        self,
        chunk_df: pd.DataFrame,
        trained_model: Any,
        feature_engineer: Any,
        model: MLModel,
        config: BatchPredictionConfig
    ) -> List[Dict[str, Any]]:
        """Make predictions for a chunk of data"""
        
        predictions = []
        
        for index, row in chunk_df.iterrows():
            try:
                # Prepare input data
                input_data = row.to_dict()
                
                # Transform data if feature engineer exists
                if feature_engineer:
                    X_transformed = feature_engineer.transform(pd.DataFrame([input_data]))
                else:
                    X_transformed = pd.DataFrame([input_data])[model.feature_names]
                
                # Make prediction
                prediction = trained_model.predict(X_transformed)[0]
                
                # Get probabilities if requested
                probabilities = None
                if (config.include_probabilities and 
                    model.problem_type.endswith("classification") and
                    hasattr(trained_model, "predict_proba")):
                    probabilities = trained_model.predict_proba(X_transformed)[0].tolist()
                
                # Create result
                result = {
                    "row_index": index,
                    "prediction": prediction.item() if hasattr(prediction, 'item') else prediction,
                    "input_data": input_data
                }
                
                if probabilities:
                    result["probabilities"] = probabilities
                
                if config.include_metadata:
                    result["metadata"] = {
                        "model_id": model.model_id,
                        "model_version": model.version,
                        "prediction_time": datetime.utcnow().isoformat()
                    }
                
                predictions.append(result)
                
            except Exception as e:
                # Handle individual prediction error
                predictions.append({
                    "row_index": index,
                    "error": str(e),
                    "input_data": row.to_dict()
                })
        
        return predictions
    
    async def _save_results(
        self,
        job: BatchJob,
        predictions: List[Dict[str, Any]],
        config: BatchPredictionConfig
    ) -> str:
        """Save prediction results to S3"""
        
        # Generate output path
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_key = f"batch-jobs/{job.user_id}/{config.model_id}/{timestamp}/results.{config.output_format}"
        
        if config.output_format.lower() == "csv":
            # Convert to CSV
            df = pd.DataFrame(predictions)
            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)
            content = csv_buffer.getvalue().encode('utf-8')
            
        elif config.output_format.lower() == "json":
            # Convert to JSON
            content = json.dumps(predictions, indent=2).encode('utf-8')
            
        else:
            raise ValueError(f"Unsupported output format: {config.output_format}")
        
        # Upload to S3
        await self.s3_service.upload_file_content(content, output_key)
        
        return output_key
    
    async def get_job_status(self, job_id: str, user_id: str) -> Optional[BatchJob]:
        """Get job status and progress"""
        
        return await BatchJob.find_one({
            "job_id": job_id,
            "user_id": user_id
        })
    
    async def list_user_jobs(
        self,
        user_id: str,
        job_type: Optional[JobType] = None,
        status: Optional[JobStatus] = None,
        limit: int = 50
    ) -> List[BatchJob]:
        """List user's batch jobs"""
        
        query = {"user_id": user_id}
        if job_type:
            query["job_type"] = job_type
        if status:
            query["status"] = status
        
        return await BatchJob.find(query).sort("-created_at").limit(limit).to_list()
    
    async def cancel_job(self, job_id: str, user_id: str) -> bool:
        """Cancel a pending or running job"""
        
        job = await BatchJob.find_one({
            "job_id": job_id,
            "user_id": user_id,
            "status": {"$in": [JobStatus.PENDING, JobStatus.RUNNING]}
        })
        
        if not job:
            return False
        
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        await job.save()
        
        return True
    
    async def retry_job(self, job_id: str, user_id: str) -> bool:
        """Retry a failed job"""
        
        job = await BatchJob.find_one({
            "job_id": job_id,
            "user_id": user_id
        })
        
        if not job or not job.can_retry():
            return False
        
        # Reset job status
        job.status = JobStatus.PENDING
        job.started_at = None
        job.completed_at = None
        job.error_message = None
        job.progress.processed_records = 0
        job.progress.success_count = 0
        job.progress.error_count = 0
        job.progress.current_chunk = 0
        
        await job.save()
        
        # Start processing again
        asyncio.create_task(self._process_batch_job(job))
        
        return True
    
    async def download_results(self, job_id: str, user_id: str) -> Optional[bytes]:
        """Download job results"""
        
        job = await BatchJob.find_one({
            "job_id": job_id,
            "user_id": user_id,
            "status": JobStatus.COMPLETED
        })
        
        if not job or not job.output_path:
            return None
        
        return await self.s3_service.download_file_content(job.output_path)