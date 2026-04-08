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

        # MySQL настройки
        self.mysql_host: str = os.getenv("MYSQL_HOST", "localhost")
        self.mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
        self.mysql_user: str = os.getenv("MYSQL_USER", "root")
        self.mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
        self.mysql_database: str = os.getenv("MYSQL_DATABASE", "gastro_ai")

        self.youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "")
        
        # Yandex OAuth
        self.yandex_client_id: str = os.getenv("YANDEX_CLIENT_ID", "")
        self.yandex_client_secret: str = os.getenv("YANDEX_CLIENT_SECRET", "")
        self.jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
        self.frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:8889")
        self.access_token_expire_minutes: int = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
        )
        self.refresh_token_expire_days: int = int(
            os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30")
        )
        self.refresh_cookie_name: str = os.getenv(
            "REFRESH_COOKIE_NAME", "gastro_refresh_token"
        )
        self.cookie_secure: bool = os.getenv(
            "COOKIE_SECURE",
            "true" if self.frontend_url.startswith("https://") else "false",
        ).lower() in {"1", "true", "yes", "on"}
        self.cookie_samesite: str = os.getenv("COOKIE_SAMESITE", "lax").lower()
        self.cors_origins = self._parse_cors_origins(
            os.getenv("CORS_ORIGINS", ""),
            self.frontend_url,
        )

        # Mattermost настройки
        self.mattermost_webhook_token: str = os.getenv("MATTERMOST_WEBHOOK_TOKEN", "")
        self.mattermost_url: str = os.getenv("MATTERMOST_URL", "")
        self.mattermost_bot_token: str = os.getenv("MATTERMOST_BOT_TOKEN", "")
        self.mattermost_prompt_file: str = os.getenv(
            "MATTERMOST_PROMPT_FILE", "./src/core/prompts/mattermost_bot_prompt.txt"
        )

    @staticmethod
    def _parse_cors_origins(raw_value: str, frontend_url: str) -> list[str]:
        origins = [value.strip() for value in raw_value.split(",") if value.strip()]
        if not origins:
            origins = [frontend_url]
        return list(dict.fromkeys(origins))
