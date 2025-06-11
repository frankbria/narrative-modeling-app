"""
PII (Personally Identifiable Information) Detection Service
Identifies and helps manage sensitive data in uploaded datasets
"""

import re
from typing import List, Dict, Any, Set
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class PIIType(Enum):
    """Types of PII we can detect"""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    DATE_OF_BIRTH = "date_of_birth"
    NAME = "name"
    ADDRESS = "address"
    MEDICAL_ID = "medical_id"
    FINANCIAL_ACCOUNT = "financial_account"


@dataclass
class PIIDetection:
    """Result of PII detection for a column"""
    column_name: str
    pii_type: PIIType
    confidence: float
    sample_count: int
    recommendation: str


class PIIDetector:
    """Detects potential PII in datasets"""
    
    def __init__(self):
        self.patterns = {
            PIIType.EMAIL: re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            PIIType.PHONE: re.compile(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'),
            PIIType.SSN: re.compile(r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b'),
            PIIType.CREDIT_CARD: re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
            PIIType.IP_ADDRESS: re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
        }
        
        # Common PII column name patterns
        self.name_patterns = {
            PIIType.EMAIL: ['email', 'e-mail', 'mail'],
            PIIType.PHONE: ['phone', 'tel', 'mobile', 'cell'],
            PIIType.SSN: ['ssn', 'social', 'social_security'],
            PIIType.NAME: ['name', 'first_name', 'last_name', 'full_name', 'firstname', 'lastname'],
            PIIType.ADDRESS: ['address', 'street', 'city', 'state', 'zip', 'postal'],
            PIIType.DATE_OF_BIRTH: ['dob', 'birth', 'birthday', 'date_of_birth'],
            PIIType.MEDICAL_ID: ['patient_id', 'medical_record', 'mrn'],
            PIIType.FINANCIAL_ACCOUNT: ['account', 'routing', 'iban', 'swift'],
        }
    
    def detect_pii_in_dataframe(self, df: pd.DataFrame, sample_size: int = 100) -> List[PIIDetection]:
        """
        Detect PII in a pandas DataFrame
        
        Args:
            df: DataFrame to analyze
            sample_size: Number of rows to sample for pattern matching
            
        Returns:
            List of PII detections
        """
        detections = []
        
        for column in df.columns:
            # Check column name first
            name_detection = self._check_column_name(column)
            if name_detection:
                detections.append(name_detection)
                continue
            
            # Sample data for pattern matching
            column_data = df[column].dropna()
            if len(column_data) == 0:
                continue
                
            # Convert to string for pattern matching
            sample_data = column_data.head(sample_size).astype(str)
            
            # Check patterns
            pattern_detection = self._check_patterns(column, sample_data)
            if pattern_detection:
                detections.append(pattern_detection)
        
        return detections
    
    def _check_column_name(self, column_name: str) -> PIIDetection:
        """Check if column name suggests PII"""
        column_lower = column_name.lower()
        
        for pii_type, patterns in self.name_patterns.items():
            for pattern in patterns:
                if pattern in column_lower:
                    return PIIDetection(
                        column_name=column_name,
                        pii_type=pii_type,
                        confidence=0.8,
                        sample_count=0,
                        recommendation=f"Column name suggests {pii_type.value}. Consider encryption or removal."
                    )
        return None
    
    def _check_patterns(self, column_name: str, data: pd.Series) -> PIIDetection:
        """Check data patterns for PII"""
        for pii_type, pattern in self.patterns.items():
            matches = data.apply(lambda x: bool(pattern.match(str(x))))
            match_count = matches.sum()
            
            if match_count > 0:
                confidence = match_count / len(data)
                if confidence > 0.1:  # More than 10% matches
                    return PIIDetection(
                        column_name=column_name,
                        pii_type=pii_type,
                        confidence=confidence,
                        sample_count=match_count,
                        recommendation=self._get_recommendation(pii_type, confidence)
                    )
        return None
    
    def _get_recommendation(self, pii_type: PIIType, confidence: float) -> str:
        """Get recommendation based on PII type and confidence"""
        if confidence > 0.8:
            return f"High confidence {pii_type.value} detected. Strongly recommend encryption or removal."
        elif confidence > 0.5:
            return f"Probable {pii_type.value} detected. Consider masking or encryption."
        else:
            return f"Possible {pii_type.value} detected. Review data and apply appropriate protection."
    
    def mask_pii(self, df: pd.DataFrame, detections: List[PIIDetection], 
                 mask_char: str = '*') -> pd.DataFrame:
        """
        Mask detected PII in DataFrame
        
        Args:
            df: DataFrame with PII
            detections: List of PII detections
            mask_char: Character to use for masking
            
        Returns:
            DataFrame with masked PII
        """
        df_masked = df.copy()
        
        for detection in detections:
            if detection.confidence > 0.5:  # Only mask high-confidence PII
                column = detection.column_name
                
                if detection.pii_type == PIIType.EMAIL:
                    df_masked[column] = df_masked[column].apply(self._mask_email)
                elif detection.pii_type == PIIType.PHONE:
                    df_masked[column] = df_masked[column].apply(self._mask_phone)
                elif detection.pii_type == PIIType.SSN:
                    df_masked[column] = df_masked[column].apply(lambda x: self._mask_sensitive(x, keep_last=4))
                elif detection.pii_type == PIIType.CREDIT_CARD:
                    df_masked[column] = df_masked[column].apply(lambda x: self._mask_sensitive(x, keep_last=4))
                else:
                    # Generic masking for other types
                    df_masked[column] = df_masked[column].apply(lambda x: self._mask_generic(x))
        
        return df_masked
    
    def _mask_email(self, email: str) -> str:
        """Mask email address keeping first char and domain"""
        if pd.isna(email):
            return email
        parts = str(email).split('@')
        if len(parts) == 2:
            masked = parts[0][0] + '*' * (len(parts[0]) - 1) + '@' + parts[1]
            return masked
        return email
    
    def _mask_phone(self, phone: str) -> str:
        """Mask phone number keeping area code"""
        if pd.isna(phone):
            return phone
        digits = re.sub(r'\D', '', str(phone))
        if len(digits) >= 10:
            return f"({digits[:3]}) ***-**{digits[-2:]}"
        return phone
    
    def _mask_sensitive(self, value: str, keep_last: int = 4) -> str:
        """Mask sensitive value keeping last N characters"""
        if pd.isna(value):
            return value
        value_str = str(value)
        if len(value_str) > keep_last:
            return '*' * (len(value_str) - keep_last) + value_str[-keep_last:]
        return value_str
    
    def _mask_generic(self, value: str) -> str:
        """Generic masking for any value"""
        if pd.isna(value):
            return value
        value_str = str(value)
        if len(value_str) > 2:
            return value_str[0] + '*' * (len(value_str) - 2) + value_str[-1]
        return '*' * len(value_str)
    
    def generate_pii_report(self, detections: List[PIIDetection]) -> Dict[str, Any]:
        """Generate a summary report of PII findings"""
        if not detections:
            return {
                "has_pii": False,
                "risk_level": "low",
                "summary": "No PII detected in the dataset.",
                "recommendations": []
            }
        
        high_risk_count = sum(1 for d in detections if d.confidence > 0.8)
        medium_risk_count = sum(1 for d in detections if 0.5 < d.confidence <= 0.8)
        
        risk_level = "high" if high_risk_count > 0 else "medium" if medium_risk_count > 0 else "low"
        
        return {
            "has_pii": True,
            "risk_level": risk_level,
            "total_pii_columns": len(detections),
            "high_risk_columns": high_risk_count,
            "summary": f"Found {len(detections)} columns with potential PII.",
            "detections": [
                {
                    "column": d.column_name,
                    "type": d.pii_type.value,
                    "confidence": round(d.confidence, 2),
                    "recommendation": d.recommendation
                }
                for d in detections
            ],
            "recommendations": self._get_general_recommendations(risk_level)
        }
    
    def _get_general_recommendations(self, risk_level: str) -> List[str]:
        """Get general recommendations based on risk level"""
        base_recommendations = [
            "Review all detected PII columns",
            "Apply encryption to sensitive data at rest",
            "Implement access controls for PII data",
            "Consider data minimization strategies"
        ]
        
        if risk_level == "high":
            base_recommendations.extend([
                "Immediate action required: Remove or encrypt high-risk PII",
                "Implement data loss prevention (DLP) measures",
                "Conduct privacy impact assessment"
            ])
        elif risk_level == "medium":
            base_recommendations.extend([
                "Plan for PII protection implementation",
                "Review data retention policies"
            ])
        
        return base_recommendations