import os
import logging
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    LOCAL_DOWNLOAD_DIR: Path = Path("./downloads")
    
    DOWNLOAD_TIMEOUT: int = 300
    YT_DLP_MAX_RETRIES: int = 3
    YT_DLP_MAX_FILESIZE: int = 500
    YT_DLP_COOKIES_FILE: Path = Path("")
    YT_DLP_COOKIES_CONTENT: str = ""
    
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
    
    @property
    def cookies_file_exists(self) -> bool:
        self._ensure_cookies_file()
        path_str = str(self.YT_DLP_COOKIES_FILE)
        return bool(path_str) and path_str != "." and self.YT_DLP_COOKIES_FILE.exists()
    
    def _ensure_cookies_file(self) -> None:
        if self.YT_DLP_COOKIES_CONTENT and self.YT_DLP_COOKIES_FILE:
            cookies_path = Path(self.YT_DLP_COOKIES_FILE)
            if not cookies_path.exists() or os.environ.get("RENDER"):
                try:
                    cookies_path.parent.mkdir(parents=True, exist_ok=True)
                    cookies_path.write_text(self.YT_DLP_COOKIES_CONTENT)
                    logger.info(f"Created cookies file from YT_DLP_COOKIES_CONTENT: {cookies_path}")
                except Exception as e:
                    logger.error(f"Failed to create cookies file: {e}")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.LOCAL_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_cookies_file()


settings = Settings()

