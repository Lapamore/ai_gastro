import os
from dotenv import load_dotenv

load_dotenv()


class AppConfig:
    def __init__(self):
        self.aitunnel_api_key: str = os.getenv("AITUNNEL_API_KEY", "")
        self.aitunnel_base_url: str = os.getenv(
            "AITUNNEL_BASE_URL", "https://api.aitunnel.ru/v1/"
        )
        self.aitunnel_model_name: str = os.getenv(
            "AITUNNEL_CHAT_MODEL", "gemini-1.5-flash-latest"
        )
        self.system_prompt_file: str = os.getenv(
            "SYSTEM_PROMPT_FILE", "./src/core/prompts/system_prompt_gastronomy.txt"
        )

        self.mongodb_connection_string: str = os.getenv(
            "MONGODB_CONNECTION_STRING", "mongodb://localhost:27017/"
        )
        self.mongodb_database_name: str = os.getenv(
            "MONGODB_DATABASE_NAME", "gastronomic_chat_ai"
        )
        self.mongodb_chat_history_collection_name: str = os.getenv(
            "MONGODB_CHAT_HISTORY_COLLECTION_NAME", "chat_histories"
        )
        self.mongodb_sessions_metadata_collection_name: str = os.getenv(
            "MONGODB_SESSIONS_METADATA_COLLECTION_NAME", "sessions_metadata"
        )

        self.youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "")
