from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    groq_api_key: str = "test_key"
    chroma_persist_dir: str = "./data/chroma"
    sqlite_db_path: str = "./data/careview.db"
    firebase_project_id: str = ""
    google_application_credentials: str = ""


settings = Settings()
