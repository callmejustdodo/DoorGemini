from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash-native-audio-preview-12-2025"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REFRESH_TOKEN: str = ""

    # Google Cloud Storage
    GCS_BUCKET_NAME: str = ""
    GCS_FACES_PREFIX: str = "faces/"

    # Owner
    OWNER_NAME: str = "Kyuhee"
    LANGUAGE: str = "en"
    DELIVERY_INSTRUCTIONS: str = "Please leave it at the door"

    # Voice
    VOICE_NAME: str = "Charon"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    # Webhook (for Telegram)
    WEBHOOK_BASE_URL: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
