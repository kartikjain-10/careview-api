from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # AI — no default; app will fail at startup if key is missing
    groq_api_key: str
    chroma_persist_dir: str = "./data/chroma"

    # DB
    sqlite_db_path: str = "./data/careview.db"

    # Firebase
    firebase_project_id: str = ""
    google_application_credentials: str = ""

    # App
    app_base_url: str = "http://localhost:3000"   # console URL for invite links

    # Demo auth — ONLY enable in non-production environments
    allow_demo_auth: bool = False

    # Email (Resend)
    resend_api_key: str = ""
    resend_from_email: str = "noreply@careview.app"

    # WhatsApp (Twilio)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    # Super-admin seed email — default empty; must be set explicitly via env
    admin_seed_email: str = ""


settings = Settings()
