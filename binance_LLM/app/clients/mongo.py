from __future__ import annotations

from pymongo import MongoClient
from pymongo.database import Database

from app.config import Settings


class MongoDatabase:
    """MongoDB Atlas connection helper."""

    def __init__(self, settings: Settings) -> None:
        self._client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=10_000)
        self._db = self._client[settings.mongodb_db_name]

    @property
    def db(self) -> Database:
        return self._db

    def ping(self) -> dict:
        """Validate connectivity to the configured MongoDB deployment."""

        return self._client.admin.command("ping")
