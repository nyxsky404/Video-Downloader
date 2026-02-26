# Video Downloader API

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| YouTube | ✅ Working | Requires cookies (see below) |
| YouTube Shorts | ✅ Working | Requires cookies |
| Twitter/X | ✅ Working | |
| Facebook | ✅ Working | |

## 🚀 Setup

### Prerequisites
- Python 3.11+
- FFmpeg installed on your system
- Node.js (for certain video platforms)

### Option 1: Local Setup

1. **Clone and navigate to project**
```bash
cd /path/to/project
```

2. **Create virtual environment**
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Create `.env` file** (copy from below or use defaults)
```bash
LOCAL_DOWNLOAD_DIR=./downloads
API_HOST=0.0.0.0
API_PORT=8000
```

5. **Setup YouTube cookies** (required for YouTube downloads)
   
   See [YouTube Cookies](#-youtube-cookies) section for detailed instructions.
   
   Quick start:
   ```bash
   # Option A: Use browser extension (recommended)
   # Install "Get cookies.txt LOCALLY" extension, export cookies to cookies.txt
   
   # Option B: Use yt-dlp
   yt-dlp --cookies-from-browser chrome "https://youtube.com" --print-to-file "%(cookies)s" cookies.txt
   ```

6. **Run the API**
```bash
python api.py
```

API will be available at: **http://localhost:8000**

### Option 2: Docker Setup

1. **Setup YouTube cookies** (required for YouTube downloads)
   
   See [YouTube Cookies](#-youtube-cookies) section for detailed instructions.
   
   ```bash
   # Make sure cookies.txt exists before starting Docker
   touch cookies.txt  # Create empty file first
   # Then export cookies using extension or yt-dlp
   ```

2. **Start the service**
```bash
docker-compose up -d
```

3. **Check logs**
```bash
docker-compose logs -f
```

4. **Stop the service**
```bash
docker-compose down
```

API will be available at: **http://localhost:8000**


## 🍪 YouTube Cookies

YouTube requires authentication to avoid bot detection. You need to provide cookies from a browser logged into YouTube.

### Method 1: Browser Extension + Incognito (Recommended)

The "Get cookies.txt LOCALLY" extension with incognito mode prevents cookie rotation issues.

**Install the extension:**
- [Chrome Web Store](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
- [Firefox Add-ons](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

**Export cookies (best practice to prevent rotation):**
1. Open a **new private/incognito window**
2. Log into YouTube in that window
3. Navigate to `https://www.youtube.com/` (keep this as the ONLY tab)
4. Use the extension to export cookies
5. Save as `cookies.txt` in your project root
6. **Close the incognito window immediately** - never reopen it

This method ensures cookies are never rotated since the session is never used again.

### Method 2: yt-dlp Built-in

```bash
# Using Chrome
yt-dlp --cookies-from-browser chrome "https://youtube.com" --print-to-file "%(cookies)s" cookies.txt

# Using Firefox
yt-dlp --cookies-from-browser firefox "https://youtube.com" --print-to-file "%(cookies)s" cookies.txt
```

### ⚠️ Important Notes

**Use a dedicated YouTube account:**
- Create a separate Google account just for this service
- Don't use your personal/main YouTube account
- This prevents cookie conflicts and protects your main account

**After exporting cookies:**
- **Don't use that browser/account for YouTube** - activity rotates cookies
- **Don't reopen the incognito session** - it will invalidate cookies
- Consider using a separate browser profile for cookie exports

**Rate limits (from yt-dlp wiki):**
- Without account: ~300 videos/hour
- With account: ~2000 videos/hour
- This API adds 5-15 second delays to avoid rate limiting

**If cookies stop working:**
- Cookies may be rotated by Google for security
- Re-export cookies and replace `cookies.txt`
- Check status: `curl http://localhost:8000/cookies/status`

### Cookie lifecycle:
- Valid for **3-6 months** typically
- Monitor via `/health` or `/cookies/status` endpoints
- Regenerate when downloads fail with auth errors
- Set a calendar reminder to refresh every 2-3 months

### Reference:
- [yt-dlp YouTube Extractors Wiki](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)
- [yt-dlp Known Issues](https://github.com/yt-dlp/yt-dlp/issues/3766)

## 📖 Usage

### 1. Download a Video
```bash
curl -X POST http://localhost:8000/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

### 2. Retrieve Downloaded Video

**Option A: Via API endpoint (works with both S3 and local storage)**
```bash
curl -O http://localhost:8000/video/video_dQw4w9WgXcQ.mp4
```

**Option B: Direct access (local storage only, when USE_S3=false)**
```bash
curl -O http://localhost:8000/downloads/video_dQw4w9WgXcQ.mp4
```

### 3. Check Service Health
```bash
curl http://localhost:8000/health
```

### 4. Check Cookie Status
```bash
curl http://localhost:8000/cookies/status
```

### 5. Access Interactive API Docs
Open in browser: **http://localhost:8000/docs**

**Note**: Downloaded videos are saved in `./downloads` folder

## ⚙️ Configuration (Optional)

Default `.env` settings:
```bash
LOCAL_DOWNLOAD_DIR=./downloads
DOWNLOAD_TIMEOUT=300
YT_DLP_MAX_RETRIES=3
YT_DLP_MAX_FILESIZE=500
YT_DLP_COOKIES_FILE=./cookies.txt
YT_DLP_COOKIES_CONTENT=   # Optional: cookies content as string (for cloud deployment)
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
LOG_FILE=video_downloader.log

# Storage Configuration
USE_S3=true               # true = S3 storage (production), false = Local storage (development)
S3_BUCKET_NAME=video-downloader-bucket
AWS_REGION=ap-south-1
```