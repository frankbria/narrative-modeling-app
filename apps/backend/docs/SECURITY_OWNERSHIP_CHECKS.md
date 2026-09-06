# Security: Ownership Check Consistency

## Overview

This document describes the ownership check security pattern implemented across service layers to prevent unauthorized access to resources.

## Problem Statement

Previously, ownership checks were performed inconsistently:
- **Service Layer**: Methods retrieved resources without ownership verification
- **API Layer**: Some routes checked `user_id` after retrieval, others didn't
- **Security Issue**: Inconsistent enforcement, easy to forget checks, no defense-in-depth

## Solution

### Opt-Out Pattern with Audit Logging

All service methods now enforce ownership checks **by default** when `user_id` is provided:

```python
async def get_model_config(
    self,
    model_id: str,
    user_id: Optional[str] = None  # Ownership check enabled when provided
) -> Optional[ModelConfig]:
    """
    Security: Enforces ownership check when user_id is provided.
    For internal operations, omit user_id parameter (logged for audit).
    """
    model = await ModelConfig.find_one(ModelConfig.model_id == model_id)

    if model is None:
        return None

    # Enforce ownership check if user_id is provided
    if user_id is not None:
        if model.user_id != user_id:
            logger.warning(
                f"Ownership check failed: User {user_id} attempted to access "
                f"model {model_id} owned by {model.user_id}"
            )
            return None
    else:
        # Log bypassed ownership check for security audit
        logger.info(
            f"Ownership check bypassed for model {model_id} "
            f"(owned by {model.user_id}). Expected for internal operations."
        )

    return model
```

### API Layer Integration

API routes now pass `current_user_id` to service methods:

```python
@router.get("/{model_id}", response_model=ModelConfigResponse)
async def get_model(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    model_service = ModelService()
    # Ownership check is enforced in service layer
    model = await model_service.get_model_config(
        model_id,
        user_id=current_user_id  # ← Ownership check enabled
    )

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found"
        )

    return model
```

## Affected Services

### ModelService (`app/services/model_service.py`)

Methods with ownership checks:
- `get_model_config(model_id, user_id=None)`
- `update_training_status(model_id, status, metrics=None, user_id=None)`
- `mark_model_trained(model_id, user_id=None)`
- `mark_model_deployed(model_id, endpoint=None, user_id=None)`
- `mark_model_archived(model_id, user_id=None)`
- `mark_model_failed(model_id, user_id=None)`
- `record_prediction(model_id, prediction_time_ms=None, user_id=None)`
- `delete_model_config(model_id, user_id=None)`
- `update_model_config(model_id, user_id=None, **update_fields)`

### VersioningService (`app/services/versioning_service.py`)

Methods with ownership checks:
- `get_version(version_id, mark_accessed=True, user_id=None)`
- `get_version_content(version_id)` — no owner predicate of its own; callers must
  establish ownership of the version first (see the route note below)
- `pin_version(version_id, user_id=None)`
- `unpin_version(version_id, user_id=None)`

### API Routes Updated

- `app/api/routes/models.py`:
  - `GET /api/v1/models/{model_id}`
  - `PUT /api/v1/models/{model_id}`
  - `GET /api/v1/models/{model_id}/performance`
  - `PUT /api/v1/models/{model_id}/deploy`

- `app/api/routes/versions.py`:
  - `GET /api/v1/versions/{version_id}`
  - `PATCH /api/v1/versions/{version_id}/pin`
  - `GET /api/v1/datasets/{dataset_id}/versions` — checks `DatasetMetadata`
    ownership in the handler before listing, and scopes both the list and the
    total count to the session user. Unknown and foreign datasets both answer
    404 so the pair is not an existence oracle (issue #446).
  - `POST /api/v1/datasets/{dataset_id}/versions` — guards ownership *before*
    reading any content (the handler copies the parent version's bytes into a
    new version owned by the caller) and scopes the parent lookup too (#447).
  - `DELETE /api/v1/versions/{version_id}` — the owner predicate lives in the
    lookup itself, which also puts it *ahead* of the `is_base_version` /
    `is_pinned` guards below: those answer 400 and would otherwise confirm a
    foreign version exists. The delete is permanent — no soft-delete flag is
    written, matching `cleanup_old_versions` (#448).

All three go through `require_owned_dataset(dataset_id, user_id)` in
`app/api/routes/versions.py`. Call it **outside** a handler's `try`: this
module's broad `except Exception` blocks would otherwise convert its 404 into
a 500.

`VersioningService.create_transformation_version` scopes its content-dedup
lookup by `user_id` as well — without that predicate a foreign version sharing
a `dataset_id` and content hash is returned to the caller and updated with
their description (#447).

## Security Benefits

1. **Defense in Depth**: Ownership checks at service layer, not just API layer
2. **Consistent Enforcement**: Opt-out pattern makes ownership checks default
3. **Audit Trail**: All bypassed ownership checks are logged for security review
4. **Fail-Safe**: Forgetting to pass `user_id` triggers audit logging (detectable)
5. **Warning Logs**: Failed ownership attempts are logged at WARNING level

## Audit Logging

### Success with Ownership Check
```
logger.info("Ownership check bypassed for model {model_id} (owned by {user_id}). Expected for internal operations.")
```

### Failed Ownership Check
```
logger.warning("Ownership check failed: User {user_id} attempted to access model {model_id} owned by {owner_id}")
```

## Internal Operations

For internal operations (background tasks, admin operations, system processes), **omit the `user_id` parameter**:

```python
# Internal operation - ownership check bypassed (logged)
model = await model_service.get_model_config(model_id)
```

This will log the bypass for security auditing but allow the operation.

## Testing

Tests that call service methods directly should:
1. **API Tests**: Pass `user_id` through authenticated client (automatic)
2. **Service Tests**: Either pass `user_id` or expect audit log messages
3. **Integration Tests**: Verify ownership failures return None/404

## Migration Notes

- **Backward Compatible**: All `user_id` parameters default to `None`
- **Existing Tests**: Continue to work without modification
- **API Routes**: Updated to pass `current_user_id`
- **No Breaking Changes**: Internal calls continue to work

## Future Enhancements

1. **Metrics Dashboard**: Track ownership check failures for security monitoring
2. **Rate Limiting**: Throttle repeated unauthorized access attempts
3. **Alerting**: Notify security team of suspicious access patterns
4. **Audit Log Export**: Regular export of bypassed ownership checks for review
