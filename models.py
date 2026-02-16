import re
from pydantic import BaseModel, HttpUrl, Field, field_validator

PLATFORM_URL_PATTERNS = {
    "youtube": re.compile(
        r"^https?://(www\.)?(m\.)?"
        r"(youtube\.com/(watch\?v=|shorts/|embed/|playlist\?list=)"
        r"|youtu\.be/)"
        r"[\w\-?&=.%/]+$",
        re.IGNORECASE,
    ),
    "facebook": re.compile(
        r"^https?://(www\.)?(m\.)?(facebook\.com/|fb\.watch/)[\w\-?&=.%/]+$",
        re.IGNORECASE,
    ),
    "x": re.compile(
        r"^(https?:\/\/)?(www\.|mobile\.)?(x\.com|twitter\.com)\/[A-Za-z0-9_]+\/status\/(\d+)",
        re.IGNORECASE,
    ),
}


class DownloadRequest(BaseModel):
    url: HttpUrl = Field(..., description="Video URL to download")

    @field_validator("url")
    @classmethod
    def validate_platform_url(cls, value: HttpUrl) -> HttpUrl:
        url = str(value)
        if not any(pattern.match(url) for pattern in PLATFORM_URL_PATTERNS.values()):
            raise ValueError("Only YouTube, Facebook, and X URLs are supported.")
        return value
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            }
        }

class DownloadResponse(BaseModel):
    status: str
    message: str
    data: dict

class VideoFileInfo(BaseModel):
    filename: str = Field(..., description="Name of the video file")
    size: int = Field(..., description="File size in bytes")
    download_url: str = Field(..., description="URL to download the video")
    
    class Config:
        json_schema_extra = {
            "example": {
                "filename": "my_video.mp4",
                "size": 10485760,
                "download_url": "/downloads/my_video.mp4"
            }
        }