import logging
from pathlib import Path
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from downloader import VideoDownloader
from models import DownloadRequest, DownloadResponse, VideoFileInfo
from config import settings

app = FastAPI()
downloader = VideoDownloader()
logger = logging.getLogger(__name__)

# Mount static files directory for video downloads
app.mount("/downloads", StaticFiles(directory=str(settings.LOCAL_DOWNLOAD_DIR)), name="downloads")


@app.get("/")
async def home():
    return {"message": "Welcome to Video Downloader API",}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/download", response_model=DownloadResponse)
async def download_video(request: DownloadRequest):
    try:
        logger.info(f"Starting download: {request.url}")
        result = downloader.download(str(request.url), request.custom_filename)
        
        if "filename" in result:
            result["download_url"] = f"/downloads/{result['filename']}"
        
        return {
            "status": "success",
            "message": "Video downloaded successfully",
            "data": result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/video/{filename}")
async def get_video(filename: str):
    try:
        file_path = Path(settings.LOCAL_DOWNLOAD_DIR) / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Video file not found")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        if not str(file_path.resolve()).startswith(str(settings.LOCAL_DOWNLOAD_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return FileResponse(
            path=str(file_path),
            media_type="video/mp4",
            filename=filename
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve video: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting API server on {settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run(
        "api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )