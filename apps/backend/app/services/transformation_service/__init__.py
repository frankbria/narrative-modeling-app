"""
Transformation Service for Visual Pipeline
"""

# Import TransformationService from parent module
import sys
import os

# Add parent directory to path to import the .py file
parent_dir = os.path.dirname(os.path.dirname(__file__))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import from the transformation_service.py file in services directory
try:
    from .. import transformation_service as ts_file
    TransformationService = ts_file.TransformationService
except ImportError:
    # Fallback: direct import
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "transformation_service_module",
        os.path.join(os.path.dirname(__file__), "../transformation_service.py")
    )
    ts_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ts_module)
    TransformationService = ts_module.TransformationService

__all__ = ['TransformationService']