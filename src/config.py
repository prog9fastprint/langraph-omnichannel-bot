from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # WhatsApp Cloud API
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = ""
    WHATSAPP_API_VERSION: str = "v18.0"

    # Telegram Bot API
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_SECRET_TOKEN: Optional[str] = None
    NGROK_URL: Optional[str] = None

    # Gemini API
    GEMINI_API_KEY: Optional[str] = None

    # OpenRouter API
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_PRIMARY_MODEL: str = "openrouter/owl-alpha"
    OPENROUTER_FALLBACK_MODELS: str = "openai/gpt-oss-120b:free,z-ai/glm-4.5-air:free"

    # Django ERP API Integration
    ERP_BASE_URL: str = "http://localhost:8000"
    ERP_USERNAME: str = ""
    ERP_PASSWORD: str = ""
    ERP_DB_URL: str = ""
    VECTOR_DB_URL: str = ""

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
