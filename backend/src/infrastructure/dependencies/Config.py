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
