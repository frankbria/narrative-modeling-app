"""
A/B Testing service for experiment management and variant assignment
"""
import random
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from scipy import stats
import numpy as np

from app.models.ab_test import ABTest, Variant, ExperimentStatus, VariantStatus
from app.models.ml_model import MLModel
from beanie import PydanticObjectId


class ABTestingService:
    """Service for managing A/B tests and experiments"""
    
    @staticmethod
    async def create_experiment(
        name: str,
        model_ids: List[str],
        user_id: str,
        primary_metric: str = "accuracy",
        traffic_split: Optional[List[float]] = None,
        description: Optional[str] = None
    ) -> ABTest:
        """Create a new A/B test experiment"""
        
        # Validate models exist
        models = []
        for model_id in model_ids:
            model = await MLModel.find_one({"model_id": model_id, "user_id": user_id})
            if not model:
                raise ValueError(f"Model {model_id} not found")
            models.append(model)
        
        # Create variants
        if traffic_split is None:
            # Equal split by default
            traffic_split = [100.0 / len(model_ids)] * len(model_ids)
        
        if len(traffic_split) != len(model_ids):
            raise ValueError("Traffic split must match number of models")
        
        if abs(sum(traffic_split) - 100.0) > 0.01:
            raise ValueError("Traffic split must sum to 100%")
        
        variants = []
        variant_names = ["Control"] + [f"Treatment {chr(65 + i)}" for i in range(len(model_ids) - 1)]
        
        for i, (model_id, traffic, variant_name) in enumerate(zip(model_ids, traffic_split, variant_names)):
            variant = Variant(
                variant_id=f"var_{PydanticObjectId()}",
                model_id=model_id,
                name=variant_name,
                traffic_percentage=traffic
            )
            variants.append(variant)
        
        # Create experiment
        experiment = ABTest(
            experiment_id=f"exp_{PydanticObjectId()}",
            name=name,
            description=description,
            user_id=user_id,
            variants=variants,
            primary_metric=primary_metric
        )
        
        await experiment.create()
        return experiment
    
    @staticmethod
    def assign_variant(experiment: ABTest, user_id: str, use_hash: bool = True) -> Variant:
        """Assign a user to a variant using consistent hashing or random assignment"""
        
        active_variants = experiment.get_active_variants()
        if not active_variants:
            raise ValueError("No active variants in experiment")
        
        if use_hash:
            # Consistent hashing for deterministic assignment
            hash_input = f"{experiment.experiment_id}:{user_id}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            assignment_value = (hash_value % 10000) / 100.0  # 0-100 range
        else:
            # Random assignment
            assignment_value = random.uniform(0, 100)
        
        # Assign based on traffic percentages
        cumulative = 0.0
        for variant in active_variants:
            cumulative += variant.traffic_percentage
            if assignment_value <= cumulative:
                return variant
        
        # Fallback to last variant (shouldn't happen with valid config)
        return active_variants[-1]
    
    @staticmethod
    async def track_prediction(
        experiment_id: str,
        variant_id: str,
        latency_ms: float,
        success: bool = True,
        custom_metrics: Optional[Dict[str, float]] = None
    ) -> None:
        """Track a prediction for a variant"""
        
        experiment = await ABTest.find_one({"experiment_id": experiment_id})
        if not experiment:
            return  # Silently fail for non-blocking tracking
        
        variant = experiment.get_variant_by_id(variant_id)
        if not variant:
            return
        
        # Update metrics
        variant.total_predictions += 1
        variant.total_latency_ms += latency_ms
        if not success:
            variant.error_count += 1
        
        # Update custom metrics
        if custom_metrics:
            for metric, value in custom_metrics.items():
                if metric not in variant.custom_metrics:
                    variant.custom_metrics[metric] = 0
                variant.custom_metrics[metric] += value
        
        experiment.updated_at = datetime.utcnow()
        await experiment.save()
    
    @staticmethod
    def calculate_statistics(
        variant_a: Variant,
        variant_b: Variant,
        metric: str = "accuracy"
    ) -> Dict[str, Any]:
        """Calculate statistical significance between two variants"""
        
        # Get metric values
        if metric == "error_rate":
            rate_a = variant_a.error_count / max(variant_a.total_predictions, 1)
            rate_b = variant_b.error_count / max(variant_b.total_predictions, 1)
        elif metric == "avg_latency":
            rate_a = variant_a.total_latency_ms / max(variant_a.total_predictions, 1)
            rate_b = variant_b.total_latency_ms / max(variant_b.total_predictions, 1)
        elif metric in variant_a.custom_metrics:
            rate_a = variant_a.custom_metrics[metric] / max(variant_a.total_predictions, 1)
            rate_b = variant_b.custom_metrics.get(metric, 0) / max(variant_b.total_predictions, 1)
        else:
            # Default to success rate
            rate_a = 1 - (variant_a.error_count / max(variant_a.total_predictions, 1))
            rate_b = 1 - (variant_b.error_count / max(variant_b.total_predictions, 1))
        
        # Calculate lift
        if rate_a > 0:
            lift = ((rate_b - rate_a) / rate_a) * 100
        else:
            lift = 0
        
        # Statistical significance (simplified for demonstration)
        # In production, use proper statistical tests based on metric type
        if variant_a.total_predictions > 30 and variant_b.total_predictions > 30:
            # Z-test for proportions
            p_pooled = ((rate_a * variant_a.total_predictions + rate_b * variant_b.total_predictions) /
                       (variant_a.total_predictions + variant_b.total_predictions))
            
            se = np.sqrt(p_pooled * (1 - p_pooled) * 
                        (1/variant_a.total_predictions + 1/variant_b.total_predictions))
            
            if se > 0:
                z_score = (rate_b - rate_a) / se
                p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))
            else:
                p_value = 1.0
        else:
            p_value = 1.0  # Not enough data
        
        return {
            "variant_a_rate": rate_a,
            "variant_b_rate": rate_b,
            "lift_percentage": lift,
            "p_value": p_value,
            "is_significant": p_value < 0.05,
            "confidence_level": 1 - p_value if p_value < 1 else 0
        }
    
    @staticmethod
    async def check_experiment_completion(experiment: ABTest) -> Tuple[bool, Optional[str]]:
        """Check if experiment has reached completion criteria"""
        
        if experiment.status != ExperimentStatus.RUNNING:
            return False, None
        
        # Check duration limit
        if experiment.test_duration_hours and experiment.started_at:
            elapsed = datetime.utcnow() - experiment.started_at
            if elapsed > timedelta(hours=experiment.test_duration_hours):
                return True, "duration_limit"
        
        # Check sample size
        all_variants_ready = all(
            v.total_predictions >= experiment.min_sample_size 
            for v in experiment.variants
        )
        
        if not all_variants_ready:
            return False, None
        
        # Check for clear winner
        if len(experiment.variants) == 2:
            stats_result = ABTestingService.calculate_statistics(
                experiment.variants[0],
                experiment.variants[1],
                experiment.primary_metric
            )
            
            if stats_result["is_significant"]:
                return True, "statistical_significance"
        
        return False, None
    
    @staticmethod
    async def complete_experiment(experiment: ABTest) -> ABTest:
        """Complete an experiment and determine the winner"""
        
        if len(experiment.variants) == 2:
            # Simple two-variant test
            stats_result = ABTestingService.calculate_statistics(
                experiment.variants[0],
                experiment.variants[1],
                experiment.primary_metric
            )
            
            if stats_result["variant_b_rate"] > stats_result["variant_a_rate"]:
                experiment.winner_variant_id = experiment.variants[1].variant_id
            else:
                experiment.winner_variant_id = experiment.variants[0].variant_id
            
            experiment.statistical_significance = 1 - stats_result["p_value"]
            experiment.lift_percentage = stats_result["lift_percentage"]
        else:
            # Multi-variant test - find best performer
            best_variant = max(
                experiment.variants,
                key=lambda v: v.custom_metrics.get(experiment.primary_metric, 0) / max(v.total_predictions, 1)
            )
            experiment.winner_variant_id = best_variant.variant_id
        
        experiment.status = ExperimentStatus.COMPLETED
        experiment.ended_at = datetime.utcnow()
        await experiment.save()
        
        return experiment
    
    @staticmethod
    async def get_experiment_metrics(experiment: ABTest) -> Dict[str, Any]:
        """Get comprehensive metrics for an experiment"""
        
        metrics = {
            "experiment_id": experiment.experiment_id,
            "name": experiment.name,
            "status": experiment.status,
            "duration": None,
            "total_predictions": 0,
            "variants": []
        }
        
        if experiment.started_at:
            if experiment.ended_at:
                duration = experiment.ended_at - experiment.started_at
            else:
                duration = datetime.utcnow() - experiment.started_at
            metrics["duration"] = duration.total_seconds()
        
        for variant in experiment.variants:
            variant_metrics = {
                "variant_id": variant.variant_id,
                "name": variant.name,
                "model_id": variant.model_id,
                "traffic_percentage": variant.traffic_percentage,
                "total_predictions": variant.total_predictions,
                "error_rate": variant.error_count / max(variant.total_predictions, 1),
                "avg_latency_ms": variant.total_latency_ms / max(variant.total_predictions, 1),
                "custom_metrics": {}
            }
            
            # Calculate averages for custom metrics
            for metric, total in variant.custom_metrics.items():
                variant_metrics["custom_metrics"][metric] = total / max(variant.total_predictions, 1)
            
            metrics["variants"].append(variant_metrics)
            metrics["total_predictions"] += variant.total_predictions
        
        # Add comparison statistics for two-variant tests
        if len(experiment.variants) == 2 and experiment.status == ExperimentStatus.RUNNING:
            stats_result = ABTestingService.calculate_statistics(
                experiment.variants[0],
                experiment.variants[1],
                experiment.primary_metric
            )
            metrics["comparison"] = stats_result
        
        return metrics