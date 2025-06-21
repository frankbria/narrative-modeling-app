# Deprecated: All DB and Beanie initialization is now handled in main.py lifespan.
# This module is kept for legacy imports only.

async def connect_to_mongo():
    """No-op: DB connection is now handled in main.py lifespan."""
    pass

async def close_mongo_connection():
    """No-op: DB connection is now handled in main.py lifespan."""
    pass
