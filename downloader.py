import logging
import uuid
from pathlib import Path
from typing import Optional, Dict
import yt_dlp

from config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class VideoDownloader:
    
    def __init__(self):
        self.download_dir = settings.LOCAL_DOWNLOAD_DIR
        logger.info(f"VideoDownloader initialized with local storage: {self.download_dir}")
    
    def download(self, url: str, custom_filename: Optional[str] = None) -> Dict[str, str]:

        logger.info(f"Starting download for URL: {url}")
        
        try:
            unique_id = str(uuid.uuid4())
            filename_template = custom_filename or f"video_{unique_id}"
            output_path = self.download_dir / f"{filename_template}.%(ext)s"
            
            ydl_opts = {
                'format': (
                    'bestvideo[height<=2160]+bestaudio/'
                    'best[height<=2160]/'
                    'bestvideo+bestaudio/'
                    'best'
                ),
                'outtmpl': str(output_path),
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
                'quiet': False,
                'no_warnings': False,
                'extract_flat': False,
                'socket_timeout': settings.DOWNLOAD_TIMEOUT,
                'retries': settings.YT_DLP_MAX_RETRIES,
                'max_filesize': settings.YT_DLP_MAX_FILESIZE * 1024 * 1024,
                'logger': logger,
                'js_runtimes': {'node': {}},
            }
            
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("Extracting video info...")
                info = ydl.extract_info(url, download=True)
                
                filename = ydl.prepare_filename(info)

                if not filename.endswith('.mp4'):
                    filename = filename.rsplit('.', 1)[0] + '.mp4'
                    
                filepath = Path(filename)
                
                if not filepath.exists():
                    raise FileNotFoundError(f"Downloaded file not found: {filepath}")
                
                
                logger.info(f"Download successful: {filepath.name}")
                
                return {
                    'status': 'success',
                    'platform': info.get('extractor', ''),
                    'video_title': info.get('title', ''),
                    'filepath': str(filepath.absolute()),
                    'filename': filepath.name,
                }
                
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"Download error: {str(e)}")
            raise Exception(f"Failed to download video: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise Exception(f"Error during download: {str(e)}")