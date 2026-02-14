import logging
from fastapi import FastAPI, HTTPException

from downloader import VideoDownloader
from models import DownloadRequest, DownloadResponse
from config import settings

app = FastAPI()
downloader = VideoDownloader()
logger = logging.getLogger(__name__)


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


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting API server on {settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run(
        "api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )