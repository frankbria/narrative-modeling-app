"""
Standardized service layer exceptions.

This module provides a consistent exception hierarchy for all service operations,
enabling proper error handling, logging, and HTTP status code mapping in routes.
"""

from typing import Optional, Dict, Any


class ServiceError(Exception):
    """
    Base exception for all service layer errors.

    Attributes:
        message: Human-readable error message
        code: Machine-readable error code for logging/monitoring
        details: Additional context about the error
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code or self.__class__.__name__.upper()
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details
        }


class NotFoundError(ServiceError):
    """
    Resource not found.

    Raised when a requested resource does not exist.
    Maps to HTTP 404.

    Example:
        raise NotFoundError(
            message="Dataset not found",
            code="DATASET_NOT_FOUND",
            details={"dataset_id": "abc123"}
        )
    """

    def __init__(
        self,
        message: str = "Resource not found",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None
    ):
        if resource_type and resource_id:
            details = details or {}
            details["resource_type"] = resource_type
            details["resource_id"] = resource_id
            if message == "Resource not found":
                message = f"{resource_type} with id '{resource_id}' not found"
        super().__init__(message, code or "NOT_FOUND", details)


class PermissionDeniedError(ServiceError):
    """
    User doesn't have permission to perform the operation.

    Raised when a user attempts to access or modify a resource they don't own
    or don't have permission to access.
    Maps to HTTP 403.

    Example:
        raise PermissionDeniedError(
            message="You don't have permission to modify this dataset",
            details={"user_id": "user123", "dataset_id": "abc123"}
        )
    """

    def __init__(
        self,
        message: str = "Permission denied",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None
    ):
        if user_id and resource_id:
            details = details or {}
            details["user_id"] = user_id
            details["resource_id"] = resource_id
        super().__init__(message, code or "PERMISSION_DENIED", details)


class ValidationError(ServiceError):
    """
    Data validation failed.

    Raised when input data fails validation rules.
    Maps to HTTP 400 or 422.

    Example:
        raise ValidationError(
            message="Invalid transformation parameters",
            details={"field": "threshold", "error": "Must be between 0 and 1"}
        )
    """

    def __init__(
        self,
        message: str = "Validation failed",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        field: Optional[str] = None,
        value: Optional[Any] = None
    ):
        if field:
            details = details or {}
            details["field"] = field
            if value is not None:
                details["value"] = str(value)
        super().__init__(message, code or "VALIDATION_ERROR", details)


class ConflictError(ServiceError):
    """
    Resource conflict.

    Raised when an operation would create a conflict, such as:
    - Duplicate resource creation
    - Version mismatch during optimistic locking
    - Concurrent modification conflict

    Maps to HTTP 409.

    Example:
        raise ConflictError(
            message="Dataset with this name already exists",
            details={"dataset_name": "my_data.csv"}
        )
    """

    def __init__(
        self,
        message: str = "Resource conflict",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        existing_id: Optional[str] = None
    ):
        if existing_id:
            details = details or {}
            details["existing_id"] = existing_id
        super().__init__(message, code or "CONFLICT", details)


class OperationError(ServiceError):
    """
    Operation failed due to external dependency or system error.

    Raised when an operation fails due to:
    - S3/storage operations
    - Database operations
    - External API calls

    Maps to HTTP 500 or 503.

    Example:
        raise OperationError(
            message="Failed to upload file to S3",
            details={"bucket": "my-bucket", "key": "path/to/file"}
        )
    """

    def __init__(
        self,
        message: str = "Operation failed",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        operation: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        if operation:
            details = details or {}
            details["operation"] = operation
        if original_error:
            details = details or {}
            details["original_error"] = str(original_error)
        super().__init__(message, code or "OPERATION_FAILED", details)


class RateLimitError(ServiceError):
    """
    Rate limit exceeded.

    Raised when a user or operation exceeds allowed rate limits.
    Maps to HTTP 429.

    Example:
        raise RateLimitError(
            message="Too many requests",
            details={"limit": 100, "window": "1 hour"}
        )
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None
    ):
        if retry_after:
            details = details or {}
            details["retry_after_seconds"] = retry_after
        super().__init__(message, code or "RATE_LIMIT_EXCEEDED", details)


class DependencyError(ServiceError):
    """
    Operation blocked by dependency constraint.

    Raised when an operation cannot proceed due to dependencies, such as:
    - Deleting a dataset that has models trained on it
    - Modifying a version that is used in training

    Maps to HTTP 409 or 424.

    Example:
        raise DependencyError(
            message="Cannot delete dataset with active models",
            details={"dataset_id": "abc123", "model_count": 3}
        )
    """

    def __init__(
        self,
        message: str = "Operation blocked by dependency",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        dependencies: Optional[list] = None
    ):
        if dependencies:
            details = details or {}
            details["dependencies"] = dependencies
        super().__init__(message, code or "DEPENDENCY_CONSTRAINT", details)
