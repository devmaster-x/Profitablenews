from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Environment Configuration
    environment: str = "development"
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False
    
    # Database Configuration
    database_url: Optional[str] = None  # For future use with persistent database
    
    # Scraping Configuration
    scraping_timeout: int = 30
    max_articles_per_source: int = 50
    user_agent: str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    
    # Scheduler Configuration
    default_scraping_time: str = "00:00"
    scheduler_check_interval: int = 60  # seconds
    
    # CORS Configuration
    cors_origins: list = ["*"]  # Allow all origins for development
    cors_credentials: bool = True
    cors_methods: list = ["*"]
    cors_headers: list = ["*"]
    
    # Logging Configuration
    log_level: str = "INFO"
    
    # Chrome/Selenium Configuration
    chrome_headless: bool = True
    chrome_no_sandbox: bool = True
    chrome_disable_dev_shm: bool = True
    chrome_disable_gpu: bool = True
    chrome_window_size: str = "1920,1080"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# Create global settings instance
settings = Settings()

# Environment variable helpers
def get_env_var(key: str, default: str = None) -> str:
    """Get environment variable with fallback to default"""
    return os.getenv(key, default)

def is_development() -> bool:
    """Check if running in development mode"""
    return settings.environment.lower() == "development"

def is_production() -> bool:
    """Check if running in production mode"""
    return settings.environment.lower() == "production" 