from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash-native-audio-preview-12-2025"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Google Cloud Storage
    GCS_BUCKET_NAME: str = ""

    # Owner
    OWNER_NAME: str = "Kyuhee"
    LANGUAGE: str = "en"
    DELIVERY_INSTRUCTIONS: str = "Please leave it at the door"

    # Voice
    VOICE_NAME: str = "Puck"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    # Webhook (for Telegram)
    WEBHOOK_BASE_URL: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
