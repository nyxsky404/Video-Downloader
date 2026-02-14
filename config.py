from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    LOCAL_DOWNLOAD_DIR: Path = Path("./downloads")
    
    DOWNLOAD_TIMEOUT: int = 300
    YT_DLP_MAX_RETRIES: int = 3
    YT_DLP_MAX_FILESIZE: int = 500
    
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "video_downloader.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )
    
    # create download directory if not exists
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.LOCAL_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()

