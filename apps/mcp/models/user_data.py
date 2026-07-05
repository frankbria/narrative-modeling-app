# apps/mcp/models/user_data.py
"""Lean read-only mirror of the backend `user_data` collection.

The MCP server only needs a dataset's owner and its server-derived S3 location to
authorize and locate a file. Undeclared collection fields are ignored on parse,
so this model stays minimal and resistant to backend schema drift.
"""

from beanie import Document


class UserData(Document):
    user_id: str
    s3_url: str
    file_path: str | None = None

    class Settings:
        name = "user_data"
