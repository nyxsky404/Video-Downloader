from typing import Optional
from pydantic import BaseModel, HttpUrl, Field


class DownloadRequest(BaseModel):
    url: HttpUrl = Field(..., description="Video URL to download")
    custom_filename: Optional[str] = Field(None, description="Custom filename (without extension)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "custom_filename": "my_video"
            }
        }

class DownloadResponse(BaseModel):
    status: str
    message: str
    data: dict