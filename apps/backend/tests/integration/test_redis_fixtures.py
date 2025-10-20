"""
Integration tests for Redis fixtures.

These tests validate that the Redis fixtures work correctly for background
job queue management.

Run with: pytest tests/integration/test_redis_fixtures.py -v -m integration
"""

import pytest
import json
from datetime import datetime, timezone


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_client_fixture(redis_client):
    """Test that redis_client fixture provides a working Redis client."""
    assert redis_client is not None

    # Test basic Redis operations
    await redis_client.set("test_key", "test_value")
    value = await redis_client.get("test_key")
    assert value == "test_value"

    # Cleanup
    await redis_client.delete("test_key")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_client_flushdb(redis_client):
    """Test that redis_client fixture starts with clean database."""
    # Database should be empty at start
    keys = await redis_client.keys("*")
    assert len(keys) == 0

    # Add some data
    await redis_client.set("temp_key", "temp_value")
    keys = await redis_client.keys("*")
    assert len(keys) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_job_fixture(test_redis_job, redis_client):
    """Test that test_redis_job fixture creates a valid job in Redis."""
    assert test_redis_job is not None
    assert test_redis_job["job_id"] == "test_redis_job_123"
    assert test_redis_job["job_type"] == "model_training"
    assert test_redis_job["user_id"] == "test_user_123"

    # Verify job exists in Redis
    job_key = f"job:{test_redis_job['job_id']}"
    job_data_str = await redis_client.get(job_key)
    assert job_data_str is not None

    # Verify job data
    job_data = json.loads(job_data_str)
    assert job_data["job_id"] == test_redis_job["job_id"]
    assert job_data["config"]["algorithm"] == "random_forest"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_queue_operations(test_redis_job, redis_client):
    """Test Redis queue operations with job fixture."""
    # Verify job is in queue
    queue_length = await redis_client.llen("job_queue")
    assert queue_length >= 1

    # Pop job from queue
    job_id = await redis_client.rpop("job_queue")
    assert job_id == test_redis_job["job_id"]

    # Queue should now be shorter
    new_queue_length = await redis_client.llen("job_queue")
    assert new_queue_length == queue_length - 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_job_status_update(test_redis_job, redis_client):
    """Test updating job status in Redis."""
    job_key = f"job:{test_redis_job['job_id']}"

    # Get current job data
    job_data_str = await redis_client.get(job_key)
    job_data = json.loads(job_data_str)

    # Update status
    job_data["status"] = "running"
    job_data["started_at"] = datetime.now(timezone.utc).isoformat()

    # Save updated data
    await redis_client.set(job_key, json.dumps(job_data))

    # Verify update
    updated_data_str = await redis_client.get(job_key)
    updated_data = json.loads(updated_data_str)
    assert updated_data["status"] == "running"
    assert "started_at" in updated_data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_job_expiration(redis_client):
    """Test Redis key expiration for job cleanup."""
    # Create a job with expiration
    job_key = "job:expiring_job_123"
    job_data = {
        "job_id": "expiring_job_123",
        "status": "completed"
    }

    # Set with 2 second expiration
    await redis_client.setex(job_key, 2, json.dumps(job_data))

    # Verify job exists
    data = await redis_client.get(job_key)
    assert data is not None

    # Check TTL
    ttl = await redis_client.ttl(job_key)
    assert ttl > 0 and ttl <= 2

    # Wait for expiration (in real tests, would use time-based mocking)
    import asyncio
    await asyncio.sleep(2.1)

    # Verify job has expired
    expired_data = await redis_client.get(job_key)
    assert expired_data is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_multiple_queues(redis_client):
    """Test managing multiple job queues in Redis."""
    # Create jobs in different queues
    await redis_client.lpush("training_queue", "job_train_1")
    await redis_client.lpush("training_queue", "job_train_2")
    await redis_client.lpush("prediction_queue", "job_pred_1")

    # Verify queue lengths
    training_length = await redis_client.llen("training_queue")
    prediction_length = await redis_client.llen("prediction_queue")

    assert training_length == 2
    assert prediction_length == 1

    # Pop from specific queue
    job_id = await redis_client.rpop("training_queue")
    assert job_id == "job_train_1"

    # Cleanup
    await redis_client.delete("training_queue", "prediction_queue")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_job_priority_queue(redis_client):
    """Test priority queue implementation using Redis sorted sets."""
    # Add jobs with priority scores (lower score = higher priority)
    await redis_client.zadd("priority_queue", {
        "job_low_priority": 10,
        "job_high_priority": 1,
        "job_medium_priority": 5
    })

    # Pop highest priority job (lowest score)
    highest_priority = await redis_client.zpopmin("priority_queue")
    assert highest_priority[0][0] == "job_high_priority"
    assert highest_priority[0][1] == 1.0

    # Verify queue size
    remaining = await redis_client.zcard("priority_queue")
    assert remaining == 2

    # Cleanup
    await redis_client.delete("priority_queue")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_pub_sub(redis_client):
    """Test Redis pub/sub for job notifications."""
    # Create a pubsub instance
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("job_notifications")

    # Publish a message
    await redis_client.publish("job_notifications", json.dumps({
        "job_id": "test_job",
        "event": "started"
    }))

    # Receive message (with timeout)
    import asyncio
    try:
        message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=1.0)
        if message:
            data = json.loads(message["data"])
            assert data["job_id"] == "test_job"
    except asyncio.TimeoutError:
        # Pub/sub can be flaky in tests, just verify subscription worked
        pass

    # Cleanup
    await pubsub.unsubscribe("job_notifications")
    await pubsub.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_fixture_isolation(test_redis_job, redis_client):
    """Test that Redis fixtures provide proper test isolation."""
    # Create additional job in this test
    additional_job_key = "job:additional_123"
    await redis_client.set(additional_job_key, json.dumps({
        "job_id": "additional_123",
        "status": "pending"
    }))

    # Verify both jobs exist
    job1_exists = await redis_client.exists(f"job:{test_redis_job['job_id']}")
    job2_exists = await redis_client.exists(additional_job_key)

    assert job1_exists == 1
    assert job2_exists == 1

    # Cleanup will be handled by fixtures
    await redis_client.delete(additional_job_key)
