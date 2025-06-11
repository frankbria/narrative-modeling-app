# Redis Caching Implementation

## Overview

This implementation adds a comprehensive Redis caching layer to improve application performance by caching expensive operations like data processing, model predictions, and user progress.

## Features

### Core Caching Operations
- **Set/Get**: Basic key-value operations with TTL support
- **Hash Operations**: For structured data like user progress
- **List Operations**: For ordered data collections
- **Pattern Deletion**: Bulk deletion using wildcard patterns
- **Atomic Operations**: Counters and increments

### Specialized Caching Methods
- **User Progress**: Cache onboarding and tutorial progress
- **Data Statistics**: Cache expensive statistical calculations
- **Model Predictions**: Cache prediction results with input hashing
- **EDA Results**: Cache exploratory data analysis results
- **Visualizations**: Cache chart and graph data

### Cache Management
- **Invalidation**: Clear cache entries for users or datasets
- **Expiration**: Automatic TTL-based cleanup
- **Monitoring**: Cache hit/miss statistics and memory usage
- **Graceful Degradation**: Application continues working if Redis is unavailable

## Architecture

### Cache Service (`RedisCacheService`)
Located in `app/services/redis_cache.py`

```python
# Basic usage
from app.services.redis_cache import cache_service

# Cache data
await cache_service.set("key", {"data": "value"}, ttl=3600)

# Retrieve data
data = await cache_service.get("key")

# Cache user progress
await cache_service.cache_user_progress(user_id, progress_data)
```

### Cache Decorator
For automatic function result caching:

```python
from app.services.redis_cache import cache_result

@cache_result("stats:{0}", ttl=7200)  # 2 hours
async def calculate_statistics(data_id):
    # Expensive operation
    return results
```

## Integration Points

### 1. Statistics Engine
- Caches dataset statistics for 2 hours
- Uses content-based cache keys for consistency
- Location: `app/services/data_processing/statistics_engine.py`

### 2. Onboarding Service
- Caches user progress for 24 hours
- Updates cache on progress changes
- Location: `app/services/onboarding_service.py`

### 3. Visualization Cache
- Dual-layer caching (Redis + MongoDB)
- 1-hour TTL for fast chart rendering
- Location: `app/services/visualization_cache.py`

### 4. Cache Management API
- RESTful endpoints for cache administration
- User-specific cache invalidation
- Cache statistics and monitoring
- Location: `app/api/routes/cache.py`

## Configuration

### Environment Variables
```bash
REDIS_URL=redis://localhost:6379  # Redis connection URL
CACHE_DEFAULT_TTL=3600            # Default TTL in seconds
```

### Docker Integration
Redis service added to `docker-compose.yml`:
```yaml
redis:
  image: redis:7.2-alpine
  ports:
    - "6379:6379"
  command: redis-server --appendonly yes
```

## Cache Keys Convention

### Pattern Structure
- `stats:{data_id}` - Dataset statistics
- `user_progress:{user_id}` - User onboarding progress  
- `predictions:{model_id}:{input_hash}` - Model predictions
- `eda:{data_id}` - EDA analysis results
- `viz:{dataset_id}:{type}:{column?}` - Visualizations

### TTL Strategies
- **User Progress**: 24 hours (frequently accessed)
- **Statistics**: 2 hours (moderate computation cost)
- **Predictions**: 1 hour (input-dependent)
- **Visualizations**: 1 hour (rendering optimization)
- **EDA Results**: 3 hours (expensive analysis)

## API Endpoints

### Cache Management
- `GET /api/v1/cache/info` - Cache statistics
- `DELETE /api/v1/cache/user/{user_id}` - Invalidate user cache
- `DELETE /api/v1/cache/data/{data_id}` - Invalidate dataset cache
- `DELETE /api/v1/cache/key/{cache_key}` - Delete specific key
- `GET /api/v1/cache/key/{cache_key}/exists` - Check key existence

## Performance Benefits

### Expected Improvements
- **Statistics Calculation**: 80-90% reduction in computation time
- **User Progress Loading**: 95% faster retrieval
- **Visualization Rendering**: 70% faster chart generation
- **Model Predictions**: 60-80% faster for repeated inputs

### Cache Hit Ratios
- User Progress: ~85% (high user activity patterns)
- Statistics: ~70% (dataset reuse)
- Visualizations: ~60% (dashboard usage)
- Predictions: ~50% (depends on input variety)

## Monitoring and Maintenance

### Health Checks
```python
# Get cache health
info = await cache_service.get_cache_info()
print(f"Memory usage: {info['used_memory_human']}")
print(f"Hit ratio: {info['keyspace_hits'] / (info['keyspace_hits'] + info['keyspace_misses'])}")
```

### Cache Cleanup
```python
# Invalidate user-specific cache
await cache_service.invalidate_user_cache(user_id)

# Invalidate dataset-specific cache  
await cache_service.invalidate_data_cache(data_id)
```

## Testing

Comprehensive test suite covering:
- Serialization/deserialization
- All cache operations (set/get/delete)
- Hash and list operations
- Specialized caching methods
- Error handling and graceful degradation
- Cache decorator functionality

Run tests: `uv run python -m pytest tests/test_services/test_redis_cache.py -v`

## Error Handling

### Graceful Degradation
- Application continues working if Redis is unavailable
- All cache operations return appropriate defaults on failure
- Errors are logged but don't affect core functionality

### Connection Management
- Automatic reconnection attempts
- Connection pooling for performance
- Proper cleanup on application shutdown

## Security Considerations

- No sensitive data stored in cache keys
- User isolation through key prefixing
- TTL ensures data doesn't persist indefinitely
- Cache access restricted to authenticated users

## Future Enhancements

1. **Cache Warming**: Pre-populate common data
2. **Compression**: Reduce memory usage for large objects
3. **Distributed Caching**: Redis Cluster support
4. **Cache Analytics**: Detailed performance metrics
5. **Smart Invalidation**: Dependency-based cache clearing