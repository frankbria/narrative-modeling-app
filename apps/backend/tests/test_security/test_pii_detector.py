"""
Tests for PII Detection Service
"""

import pytest
import pandas as pd
from app.services.security.pii_detector import PIIDetector, PIIType


class TestPIIDetector:
    """Test cases for PII detection"""
    
    def setup_method(self):
        self.detector = PIIDetector()
    
    def test_email_detection(self):
        """Test email PII detection"""
        df = pd.DataFrame({
            'user_email': ['john@example.com', 'jane@test.org', 'user@company.co.uk'],
            'other_data': [1, 2, 3]
        })
        
        detections = self.detector.detect_pii_in_dataframe(df)
        
        # Should detect email column
        email_detections = [d for d in detections if d.pii_type == PIIType.EMAIL]
        assert len(email_detections) == 1
        assert email_detections[0].column_name == 'user_email'
        assert email_detections[0].confidence >= 0.8
    
    def test_phone_detection(self):
        """Test phone number PII detection"""
        df = pd.DataFrame({
            'phone': ['(555) 123-4567', '555-987-6543', '+1-555-111-2222'],
            'other_data': [1, 2, 3]
        })
        
        detections = self.detector.detect_pii_in_dataframe(df)
        
        phone_detections = [d for d in detections if d.pii_type == PIIType.PHONE]
        assert len(phone_detections) == 1
        assert phone_detections[0].column_name == 'phone'
    
    def test_ssn_detection(self):
        """Test SSN PII detection"""
        df = pd.DataFrame({
            'ssn': ['123-45-6789', '987-65-4321', '555-44-3333'],
            'other_data': [1, 2, 3]
        })
        
        detections = self.detector.detect_pii_in_dataframe(df)
        
        ssn_detections = [d for d in detections if d.pii_type == PIIType.SSN]
        assert len(ssn_detections) == 1
        assert ssn_detections[0].column_name == 'ssn'
    
    def test_column_name_detection(self):
        """Test PII detection based on column names"""
        df = pd.DataFrame({
            'first_name': ['John', 'Jane', 'Bob'],
            'email_address': ['a', 'b', 'c'],  # Not real emails, but column name suggests PII
            'phone_number': ['123', '456', '789'],
            'regular_data': [1, 2, 3]
        })
        
        detections = self.detector.detect_pii_in_dataframe(df)
        
        # Should detect based on column names
        column_names = [d.column_name for d in detections]
        assert 'first_name' in column_names
        assert 'email_address' in column_names
        assert 'phone_number' in column_names
        assert 'regular_data' not in column_names
    
    def test_no_pii_detection(self):
        """Test that clean data doesn't trigger false positives"""
        df = pd.DataFrame({
            'product_id': [1001, 1002, 1003],
            'price': [19.99, 29.99, 39.99],
            'category': ['electronics', 'books', 'clothing']
        })
        
        detections = self.detector.detect_pii_in_dataframe(df)
        assert len(detections) == 0
    
    def test_email_masking(self):
        """Test email masking functionality"""
        email = "john.doe@example.com"
        masked = self.detector._mask_email(email)
        
        assert masked.startswith('j')
        assert '@example.com' in masked
        assert '*' in masked
    
    def test_phone_masking(self):
        """Test phone number masking"""
        phone = "(555) 123-4567"
        masked = self.detector._mask_phone(phone)
        
        assert '(555)' in masked
        assert '67' in masked  # Last 2 digits
        assert '*' in masked
    
    def test_pii_report_generation(self):
        """Test PII report generation"""
        df = pd.DataFrame({
            'email': ['user@test.com', 'admin@site.org'],
            'phone': ['555-1234', '555-5678'],
            'data': [1, 2]
        })
        
        detections = self.detector.detect_pii_in_dataframe(df)
        report = self.detector.generate_pii_report(detections)
        
        assert report['has_pii'] is True
        assert report['total_pii_columns'] > 0
        assert 'detections' in report
        assert 'recommendations' in report
    
    def test_mask_pii_dataframe(self):
        """Test masking PII in entire DataFrame"""
        df = pd.DataFrame({
            'email': ['john@example.com', 'jane@test.org'],
            'phone': ['555-1234', '555-5678'],
            'name': ['John Doe', 'Jane Smith'],
            'safe_data': [1, 2]
        })
        
        detections = self.detector.detect_pii_in_dataframe(df)
        masked_df = self.detector.mask_pii(df, detections)
        
        # Original should be unchanged
        assert df.iloc[0]['email'] == 'john@example.com'
        
        # Masked should be different
        assert masked_df.iloc[0]['email'] != 'john@example.com'
        assert '@example.com' in masked_df.iloc[0]['email']  # Domain preserved
        
        # Safe data should be unchanged
        assert masked_df.iloc[0]['safe_data'] == 1