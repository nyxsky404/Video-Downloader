import logging
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
    
    def download(self, url: str, custom_filename: Optional[str] = None) -> Dict:

        logger.info(f"Starting download for URL: {url}")
        
        try:
            if custom_filename:
                output_template = f"{custom_filename}_%(playlist_index|)s%(title).50s_%(id)s.%(ext)s"
            else:
                output_template = "%(playlist_index|)svideo_%(id)s.%(ext)s"
            
            output_path = self.download_dir / output_template
            
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
                'noplaylist': False,
                'yes_playlist': True,
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
                logger.info("Extracting video/playlist info...")
                info = ydl.extract_info(url, download=True)
                is_playlist = 'entries' in info
                
                if is_playlist:
                    entries = list(info['entries'])
                    video_count = len(entries)
                    logger.info(f"Playlist download successful: {video_count} videos")
                    
                    filenames = []
                    download_urls = []
                    
                    for entry in entries:
                        if entry:
                            filename = ydl.prepare_filename(entry)
                            if not filename.endswith('.mp4'):
                                filename = filename.rsplit('.', 1)[0] + '.mp4'
                            
                            filepath = Path(filename)
                            if filepath.exists():
                                filenames.append(filepath.name)
                                download_urls.append(f"/downloads/{filepath.name}")
                    
                    return {
                        'status': 'success',
                        'type': 'playlist',
                        'platform': info.get('extractor', ''),
                        'playlist_title': info.get('title', ''),
                        'video_count': len(filenames),
                        'filenames': filenames,
                        'download_urls': download_urls,
                    }
                else:
                    filename = ydl.prepare_filename(info)

                    if not filename.endswith('.mp4'):
                        filename = filename.rsplit('.', 1)[0] + '.mp4'
                        
                    filepath = Path(filename)
                    
                    if not filepath.exists():
                        raise FileNotFoundError(f"Downloaded file not found: {filepath}")
                    
                    logger.info(f"Download successful: {filepath.name}")
                    
                    return {
                        'status': 'success',
                        'type': 'video',
                        'platform': info.get('extractor', ''),
                        'video_title': info.get('title', ''),
                        'filename': filepath.name,
                        'download_url': f"/downloads/{filepath.name}"
                    }
                
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"Download error: {str(e)}")
            raise Exception(f"Failed to download video: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise Exception(f"Error during download: {str(e)}")
