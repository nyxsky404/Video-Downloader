import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

from downloader import VideoDownloader
from models import DownloadRequest, DownloadResponse
from config import settings
from cookies_checker import check_cookies
from storage import get_storage_backend

app = FastAPI()
downloader = VideoDownloader()
storage = get_storage_backend()
logger = logging.getLogger(__name__)

if not settings.USE_S3:
    app.mount("/downloads", StaticFiles(directory=str(settings.LOCAL_DOWNLOAD_DIR)), name="downloads")

@app.get("/")
async def home():
    return {"message": "Welcome to Video Downloader API",}


@app.get("/health")
async def health():
    cookies_status = check_cookies(settings.YT_DLP_COOKIES_FILE)
    return {
        "status": "healthy",
        "cookies": cookies_status.to_dict()
    }


@app.get("/cookies/status")
async def cookies_status():
    status = check_cookies(settings.YT_DLP_COOKIES_FILE)
    return status.to_dict()


@app.get("/cookies/test")
async def cookies_test():
    status = check_cookies(settings.YT_DLP_COOKIES_FILE, test_with_youtube=True)
    return status.to_dict()


@app.post("/download", response_model=DownloadResponse)
async def download_video(request: DownloadRequest):
    try:
        logger.info(f"Starting download: {request.url}")
        result = downloader.download(str(request.url))
        
        if result.get('type') == 'playlist':
            message = f"Playlist downloaded successfully ({result.get('video_count', 0)} videos)"
        else:
            message = "Video downloaded successfully"
        
        return {
            "status": "success",
            "message": message,
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
        if not Path(filename).suffix:
            filename = f"{filename}.mp4"
        
        if settings.USE_S3:
            if not storage.file_exists(filename):
                raise HTTPException(status_code=404, detail="Video file not found")
            
            return {"url": storage.get_file_url(filename)}
        
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