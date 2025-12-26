"""
Domain detection utility for AI-powered feature suggestions.

Analyzes dataset characteristics to detect the business domain,
enabling domain-specific feature templates and suggestions.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class Domain(str, Enum):
    """Supported data domains"""
    FINANCIAL = "financial"
    HEALTHCARE = "healthcare"
    RETAIL = "retail"
    REAL_ESTATE = "real_estate"
    HR = "hr"
    MARKETING = "marketing"
    MANUFACTURING = "manufacturing"
    TRANSPORTATION = "transportation"
    EDUCATION = "education"
    GENERAL = "general"


@dataclass
class DomainDetectionResult:
    """Result of domain detection"""
    domain: Domain
    confidence: float
    evidence: List[str]
    suggested_features: List[Dict[str, Any]]
    metadata: Dict[str, Any]


# Domain keyword patterns
DOMAIN_PATTERNS: Dict[Domain, Dict[str, List[str]]] = {
    Domain.FINANCIAL: {
        "column_keywords": [
            "price", "cost", "revenue", "profit", "margin", "balance",
            "transaction", "payment", "amount", "fee", "interest", "rate",
            "loan", "credit", "debit", "investment", "stock", "portfolio",
            "dividend", "yield", "forex", "currency", "exchange", "trade",
            "asset", "liability", "equity", "cash", "flow", "budget"
        ],
        "value_patterns": [
            r"^\$[\d,]+\.?\d*$",  # Currency format
            r"^[\d,]+\.\d{2}$",   # Decimal with 2 places
            r"^\d{4}-\d{2}-\d{2}$",  # Date patterns common in finance
        ]
    },
    Domain.HEALTHCARE: {
        "column_keywords": [
            "patient", "diagnosis", "treatment", "medication", "drug",
            "dosage", "prescription", "symptom", "condition", "disease",
            "hospital", "clinic", "doctor", "nurse", "physician",
            "blood", "pressure", "pulse", "temperature", "bmi",
            "weight", "height", "age", "gender", "allergy", "lab",
            "test", "result", "appointment", "visit", "insurance"
        ],
        "value_patterns": [
            r"^ICD-?\d+",  # ICD codes
            r"^[A-Z]\d{2}(\.\d+)?$",  # ICD-10 format
        ]
    },
    Domain.RETAIL: {
        "column_keywords": [
            "product", "item", "sku", "quantity", "order", "customer",
            "cart", "purchase", "sale", "discount", "coupon", "promotion",
            "inventory", "stock", "warehouse", "shipping", "delivery",
            "category", "brand", "vendor", "supplier", "return", "refund",
            "review", "rating", "wishlist", "checkout"
        ],
        "value_patterns": [
            r"^SKU-?\d+",  # SKU codes
            r"^ORD-?\d+",  # Order IDs
        ]
    },
    Domain.REAL_ESTATE: {
        "column_keywords": [
            "property", "house", "apartment", "condo", "bedroom", "bathroom",
            "sqft", "square", "feet", "acre", "lot", "garage", "parking",
            "listing", "mortgage", "rent", "lease", "landlord", "tenant",
            "address", "zipcode", "neighborhood", "location", "lat", "lng",
            "longitude", "latitude", "year_built", "floors", "stories"
        ],
        "value_patterns": [
            r"^\d{5}(-\d{4})?$",  # ZIP codes
        ]
    },
    Domain.HR: {
        "column_keywords": [
            "employee", "salary", "compensation", "bonus", "benefit",
            "department", "title", "position", "manager", "team",
            "hire", "termination", "tenure", "performance", "review",
            "training", "skill", "certification", "education", "degree",
            "experience", "resume", "candidate", "interview", "offer"
        ],
        "value_patterns": []
    },
    Domain.MARKETING: {
        "column_keywords": [
            "campaign", "channel", "impression", "click", "conversion",
            "ctr", "cpc", "roi", "lead", "prospect", "segment",
            "email", "open", "bounce", "unsubscribe", "engagement",
            "reach", "audience", "demographic", "target", "ad", "adset",
            "creative", "content", "social", "seo", "sem"
        ],
        "value_patterns": []
    },
    Domain.MANUFACTURING: {
        "column_keywords": [
            "machine", "equipment", "sensor", "temperature", "pressure",
            "vibration", "defect", "quality", "inspection", "batch",
            "production", "yield", "downtime", "maintenance", "failure",
            "cycle", "throughput", "efficiency", "waste", "scrap"
        ],
        "value_patterns": []
    },
    Domain.TRANSPORTATION: {
        "column_keywords": [
            "vehicle", "route", "trip", "distance", "duration", "speed",
            "fuel", "mileage", "driver", "passenger", "pickup", "dropoff",
            "origin", "destination", "tracking", "eta", "delay", "traffic",
            "fleet", "dispatch", "cargo", "freight", "shipment"
        ],
        "value_patterns": []
    },
    Domain.EDUCATION: {
        "column_keywords": [
            "student", "teacher", "course", "class", "grade", "score",
            "exam", "test", "assignment", "homework", "attendance",
            "enrollment", "graduation", "gpa", "credit", "semester",
            "major", "minor", "degree", "faculty", "department"
        ],
        "value_patterns": []
    }
}

# Domain-specific feature templates
DOMAIN_FEATURE_TEMPLATES: Dict[Domain, List[Dict[str, Any]]] = {
    Domain.FINANCIAL: [
        {
            "name": "price_change_pct",
            "description": "Percentage change in price",
            "formula": "(current_price - previous_price) / previous_price * 100",
            "feature_type": "mathematical",
            "required_columns": ["price"]
        },
        {
            "name": "profit_margin",
            "description": "Profit margin ratio",
            "formula": "(revenue - cost) / revenue",
            "feature_type": "mathematical",
            "required_columns": ["revenue", "cost"]
        },
        {
            "name": "log_amount",
            "description": "Log-transformed transaction amount to reduce skewness",
            "formula": "log(amount + 1)",
            "feature_type": "mathematical",
            "required_columns": ["amount"]
        }
    ],
    Domain.HEALTHCARE: [
        {
            "name": "bmi_category",
            "description": "BMI category based on standard thresholds",
            "formula": "categorize(bmi, [18.5, 25, 30])",
            "feature_type": "binning",
            "required_columns": ["bmi"]
        },
        {
            "name": "age_group",
            "description": "Age group for demographic analysis",
            "formula": "categorize(age, [18, 35, 50, 65])",
            "feature_type": "binning",
            "required_columns": ["age"]
        },
        {
            "name": "days_since_visit",
            "description": "Days since last medical visit",
            "formula": "current_date - last_visit_date",
            "feature_type": "time_based",
            "required_columns": ["last_visit_date"]
        }
    ],
    Domain.RETAIL: [
        {
            "name": "order_value_per_item",
            "description": "Average value per item in order",
            "formula": "order_total / item_count",
            "feature_type": "mathematical",
            "required_columns": ["order_total", "quantity"]
        },
        {
            "name": "is_weekend_order",
            "description": "Whether order was placed on weekend",
            "formula": "day_of_week in [5, 6]",
            "feature_type": "time_based",
            "required_columns": ["order_date"]
        },
        {
            "name": "customer_order_count",
            "description": "Count of orders per customer",
            "formula": "count() group by customer_id",
            "feature_type": "aggregation",
            "required_columns": ["customer_id"]
        }
    ],
    Domain.REAL_ESTATE: [
        {
            "name": "price_per_sqft",
            "description": "Price per square foot",
            "formula": "price / sqft",
            "feature_type": "mathematical",
            "required_columns": ["price", "sqft"]
        },
        {
            "name": "property_age",
            "description": "Age of the property in years",
            "formula": "current_year - year_built",
            "feature_type": "time_based",
            "required_columns": ["year_built"]
        },
        {
            "name": "room_count",
            "description": "Total room count",
            "formula": "bedrooms + bathrooms",
            "feature_type": "mathematical",
            "required_columns": ["bedrooms", "bathrooms"]
        }
    ],
    Domain.HR: [
        {
            "name": "tenure_years",
            "description": "Years of employment",
            "formula": "(current_date - hire_date) / 365",
            "feature_type": "time_based",
            "required_columns": ["hire_date"]
        },
        {
            "name": "salary_by_department",
            "description": "Relative salary within department",
            "formula": "salary / mean(salary) group by department",
            "feature_type": "aggregation",
            "required_columns": ["salary", "department"]
        }
    ],
    Domain.MARKETING: [
        {
            "name": "conversion_rate",
            "description": "Click to conversion rate",
            "formula": "conversions / clicks",
            "feature_type": "mathematical",
            "required_columns": ["conversions", "clicks"]
        },
        {
            "name": "cost_per_conversion",
            "description": "Cost per conversion/acquisition",
            "formula": "spend / conversions",
            "feature_type": "mathematical",
            "required_columns": ["spend", "conversions"]
        }
    ],
    Domain.MANUFACTURING: [
        {
            "name": "defect_rate",
            "description": "Defect rate per batch",
            "formula": "defects / total_produced",
            "feature_type": "mathematical",
            "required_columns": ["defects", "total_produced"]
        },
        {
            "name": "sensor_deviation",
            "description": "Deviation from normal sensor reading",
            "formula": "abs(reading - mean_reading) / std_reading",
            "feature_type": "mathematical",
            "required_columns": ["sensor_reading"]
        }
    ],
    Domain.TRANSPORTATION: [
        {
            "name": "avg_speed",
            "description": "Average speed for trip",
            "formula": "distance / duration",
            "feature_type": "mathematical",
            "required_columns": ["distance", "duration"]
        },
        {
            "name": "fuel_efficiency",
            "description": "Fuel consumption per distance",
            "formula": "fuel_used / distance",
            "feature_type": "mathematical",
            "required_columns": ["fuel_used", "distance"]
        }
    ],
    Domain.EDUCATION: [
        {
            "name": "grade_improvement",
            "description": "Improvement from previous assessment",
            "formula": "current_grade - previous_grade",
            "feature_type": "mathematical",
            "required_columns": ["grade"]
        },
        {
            "name": "attendance_rate",
            "description": "Attendance percentage",
            "formula": "attended / total_classes * 100",
            "feature_type": "mathematical",
            "required_columns": ["attended", "total_classes"]
        }
    ],
    Domain.GENERAL: []
}


class DomainDetector:
    """Automatically detect the domain of a dataset based on column names and values"""

    def __init__(self):
        self.domain_patterns = DOMAIN_PATTERNS
        self.feature_templates = DOMAIN_FEATURE_TEMPLATES

    def detect_domain(
        self,
        df: pd.DataFrame,
        column_names: Optional[List[str]] = None
    ) -> DomainDetectionResult:
        """
        Detect the domain of a dataset.

        Args:
            df: Input dataframe
            column_names: Column names to analyze (uses df.columns if not provided)

        Returns:
            DomainDetectionResult with detected domain and confidence
        """
        if column_names is None:
            column_names = list(df.columns)

        # Score each domain
        domain_scores: Dict[Domain, Tuple[float, List[str]]] = {}

        for domain in Domain:
            if domain == Domain.GENERAL:
                continue

            score, evidence = self._score_domain(df, column_names, domain)
            domain_scores[domain] = (score, evidence)

        # Find best matching domain
        best_domain = Domain.GENERAL
        best_score = 0.0
        best_evidence: List[str] = []

        for domain, (score, evidence) in domain_scores.items():
            if score > best_score:
                best_score = score
                best_domain = domain
                best_evidence = evidence

        # Require minimum confidence threshold
        confidence = min(best_score, 1.0)
        if confidence < 0.3:
            best_domain = Domain.GENERAL
            confidence = 0.5
            best_evidence = ["No strong domain indicators detected"]

        # Get suggested features for the domain
        suggested_features = self._get_applicable_features(df, column_names, best_domain)

        return DomainDetectionResult(
            domain=best_domain,
            confidence=confidence,
            evidence=best_evidence,
            suggested_features=suggested_features,
            metadata={
                "all_scores": {d.value: s for d, (s, _) in domain_scores.items()},
                "column_count": len(column_names),
                "row_count": len(df)
            }
        )

    def _score_domain(
        self,
        df: pd.DataFrame,
        column_names: List[str],
        domain: Domain
    ) -> Tuple[float, List[str]]:
        """Score how well a dataset matches a domain"""
        patterns = self.domain_patterns.get(domain, {"column_keywords": [], "value_patterns": []})
        keywords = patterns.get("column_keywords", [])
        value_patterns = patterns.get("value_patterns", [])

        score = 0.0
        evidence: List[str] = []

        # Score based on column name matches
        columns_lower = [col.lower().replace("_", " ").replace("-", " ") for col in column_names]

        keyword_matches = 0
        for keyword in keywords:
            for col, col_lower in zip(column_names, columns_lower):
                if keyword in col_lower:
                    keyword_matches += 1
                    if len(evidence) < 5:
                        evidence.append(f"Column '{col}' matches keyword '{keyword}'")
                    break

        if keyword_matches > 0:
            # More matches = higher score, but with diminishing returns
            score += min(0.6, keyword_matches * 0.15)

        # Score based on value patterns
        if value_patterns:
            pattern_matches = 0
            for col in df.columns:
                if df[col].dtype == object:
                    sample = df[col].dropna().head(100).astype(str)
                    for pattern in value_patterns:
                        matches = sample.str.match(pattern, na=False).sum()
                        if matches > len(sample) * 0.3:
                            pattern_matches += 1
                            if len(evidence) < 5:
                                evidence.append(f"Column '{col}' matches value pattern")
                            break

            if pattern_matches > 0:
                score += min(0.4, pattern_matches * 0.1)

        return score, evidence

    def _get_applicable_features(
        self,
        df: pd.DataFrame,
        column_names: List[str],
        domain: Domain
    ) -> List[Dict[str, Any]]:
        """Get domain-specific feature templates that can be applied to this dataset"""
        templates = self.feature_templates.get(domain, [])
        applicable: List[Dict[str, Any]] = []

        columns_lower = {col.lower().replace("_", ""): col for col in column_names}

        for template in templates:
            required = template.get("required_columns", [])

            # Check if required columns exist (fuzzy match)
            matching_columns = {}
            for req_col in required:
                req_lower = req_col.lower().replace("_", "")
                # Try exact match first
                if req_lower in columns_lower:
                    matching_columns[req_col] = columns_lower[req_lower]
                else:
                    # Try partial match
                    for col_key, col_name in columns_lower.items():
                        if req_lower in col_key or col_key in req_lower:
                            matching_columns[req_col] = col_name
                            break

            if len(matching_columns) >= len(required) * 0.5:  # At least 50% match
                applicable_template = template.copy()
                applicable_template["matching_columns"] = matching_columns
                applicable_template["can_apply"] = len(matching_columns) == len(required)
                applicable.append(applicable_template)

        return applicable

    def get_domain_description(self, domain: Domain) -> str:
        """Get a human-readable description of a domain"""
        descriptions = {
            Domain.FINANCIAL: "Financial data including transactions, prices, investments, and monetary metrics",
            Domain.HEALTHCARE: "Healthcare and medical data including patient records, diagnoses, and treatments",
            Domain.RETAIL: "Retail and e-commerce data including products, orders, and customer transactions",
            Domain.REAL_ESTATE: "Real estate and property data including listings, prices, and property features",
            Domain.HR: "Human resources data including employees, salaries, and performance metrics",
            Domain.MARKETING: "Marketing and advertising data including campaigns, conversions, and engagement metrics",
            Domain.MANUFACTURING: "Manufacturing data including production metrics, quality control, and sensor readings",
            Domain.TRANSPORTATION: "Transportation and logistics data including routes, trips, and fleet management",
            Domain.EDUCATION: "Educational data including student records, grades, and course information",
            Domain.GENERAL: "General purpose data without specific domain characteristics"
        }
        return descriptions.get(domain, "Unknown domain")


# Singleton instance
domain_detector = DomainDetector()
