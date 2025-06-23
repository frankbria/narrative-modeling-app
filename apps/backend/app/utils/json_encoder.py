"""
Custom JSON encoder to handle numpy and other special types
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, date
from decimal import Decimal
from bson import ObjectId


class NumpyJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types and other special cases"""
    
    def default(self, obj):
        # Handle numpy types
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        
        # Handle datetime types
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        
        # Handle Decimal
        elif isinstance(obj, Decimal):
            return float(obj)
        
        # Handle MongoDB ObjectId
        elif isinstance(obj, ObjectId):
            return str(obj)
        
        # Let the base class default method raise the TypeError
        return super().default(obj)


def convert_numpy_types(obj):
    """
    Recursively convert numpy types in a dictionary or list to Python types
    """
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif pd.isna(obj):
        # Handle pandas NaN/None values
        return None
    elif hasattr(obj, 'item'):
        # Handle numpy scalars
        try:
            return obj.item()
        except:
            return str(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, ObjectId):
        return str(obj)
    else:
        return obj