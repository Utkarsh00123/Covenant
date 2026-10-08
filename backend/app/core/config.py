from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "COVENANT API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    ENVIRONMENT: str = "development"
    
    # Security & Auth (Placeholder for future)
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION"
    
    # Database Configuration
    DATABASE_URL: str
    
    # Geminiapi Configuration
    GEMINI_API_KEY: str
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 20

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()