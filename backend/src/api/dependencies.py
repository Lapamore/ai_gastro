from src.infrastructure.impl.mongodb_client.MongoDbImpl import MongoDBService

_db_service: MongoDBService | None = None


def set_db_service(service: MongoDBService):
    global _db_service
    _db_service = service


def get_db_service() -> MongoDBService:
    if _db_service is None:
        raise RuntimeError("Database service not initialized")
    return _db_service
