from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import settings
from typing import Optional

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect_db() -> None:
    """
    Initialize MongoDB connection
    """
    global _client, _db

    try:
        _client = AsyncIOMotorClient(settings.MONGODB_URL)
        _db = _client[settings.DATABASE_NAME]

        # Test connection
        await _client.admin.command("ping")
        print("✅ MongoDB connected successfully")

    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        raise


async def close_db() -> None:
    """
    Close MongoDB connection
    """
    global _client

    if _client:
        _client.close()
        print("🛑 MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """
    Get MongoDB database instance
    """
    if _db is None:
        raise RuntimeError("❌ Database not initialized. Call connect_db() first.")

    return _db
