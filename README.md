# Video Downloader API

A simple and efficient video downloader API built with FastAPI and yt-dlp.

## API Usage

### Download Video

#### 1. Simple Download
```bash
curl -X POST http://localhost:8000/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

#### 2. Download with Custom Filename
```bash
curl -X POST http://localhost:8000/download \
  -H "Content-Type: application/json" \
  -d '{"url": "VIDEO_URL", "custom_filename": "my_video"}'
```

### 3. Download Specific Video
```bash
# Browser-friendly download URL
curl -O http://localhost:8000/video/my_video.mp4

# Or access static files directly
curl -O http://localhost:8000/downloads/my_video.mp4
```

### Health Check
```bash
curl http://localhost:8000/health
```

## 🐳 Docker

### 1. Build and start
```bash
docker-compose up -d
```

### 2. Check logs
```bash
docker-compose logs -f
```

### 3. Stop
```bash
docker-compose down
```

## 🔗 Useful Links

- **API Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health
- **Downloads**: http://localhost:8000/downloads

**Downloads location**: `./downloads` folder on your local machine (mapped from container)

> **Note**: Make sure you have `.env` file created before running Docker!

## 📋 Environment Variables

Create a `.env` file with the following variables:

```bash
# Storage
LOCAL_DOWNLOAD_DIR=./downloads
DOWNLOAD_TIMEOUT=300

# yt-dlp Settings
YT_DLP_MAX_RETRIES=3
YT_DLP_MAX_FILESIZE=500

# API Config
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
LOG_FILE=video_downloader.log
```