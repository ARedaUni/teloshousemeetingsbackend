from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Audio Processing API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Google Cloud Settings
    GOOGLE_APPLICATION_CREDENTIALS: str = "service-account.json"
    PROJECT_ID: str = "telostack"
    LOCATION: str = "us-central1"
    BUCKET_NAME: str = "telostack-audio-processing"
    
    # Jina AI Settings
    JINA_AUTH_TOKEN: str = 'jina_d64d628a2405483c94084540af7cf3e2xoH8_Gia_Jq-Srn44FxoPp26uJxG'
    JINA_EMBEDDING_URL: str = "https://api.jina.ai/v1/embeddings"
    JINA_MODEL_NAME: str = "jina-embeddings-v3"
    
    # Processing Settings
    TEMP_DIR: str = "/tmp"
    MIN_SIMILARITY_THRESHOLD: float = 0.35
    TIME_WINDOW_DAYS: int = 365
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()