from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Configuration
    api_key: str = "NISHKARSH_eTKQjVzWOQEB6aploRZ@r)X1A4(r)MC1"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "YouTube API Service"
    api_version: str = "1.0.0"
    
    # YouTube Data V3 API
    youtube_data_v3_api_key: str = ""

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60

    # Caching Configuration
    cache_enabled: bool = False
    cache_type: str = "memory"  # memory or redis
    cache_ttl_seconds: int = 3600
    redis_url: Optional[str] = None

    # YouTube Configuration
    ytdlp_auto_update: bool = True
    default_audio_format: str = "bestaudio/best"
    default_video_format: str = "bestvideo+bestaudio/best"
    max_results: int = 10
    region_fallback: bool = True
    
    # Enhanced extraction settings
    use_cookies: bool = True
    cookie_file: Optional[str] = "app/cookies.txt"
    source_address: str = "0.0.0.0"
    enable_ipv4: bool = True
    max_retries: int = 3
    retry_delay: int = 1  # seconds
    
    # Client fallback order
    client_order: str = "android,web,ios,tv"

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "json"

    # Security
    allowed_origins: str = "*"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
