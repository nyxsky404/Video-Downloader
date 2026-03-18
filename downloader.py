import logging
from pathlib import Path
from typing import Dict
import yt_dlp

from config import settings
from cookies_checker import check_cookies
from storage import get_storage_backend, StorageBackend

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
    
    def _find_downloaded_file(self, video_id: str, expected_filename: str) -> Path:
        """Find the actual downloaded file, handling yt-dlp's format code suffixes."""
        # First check for the expected merged file
        if not expected_filename.endswith('.mp4'):
            expected_filename = expected_filename.rsplit('.', 1)[0] + '.mp4'
        expected_path = Path(expected_filename)
        if expected_path.exists():
            return expected_path
        
        # Check for incomplete downloads (.part files)
        part_files = list(self.download_dir.glob(f'*{video_id}*.part'))
        if part_files:
            logger.warning(f"Incomplete download detected for video {video_id}: {[f.name for f in part_files]}")
        
        # Search for any file matching *{video_id}.* pattern
        # Exclude .part files (incomplete downloads)
        matching_files = list(self.download_dir.glob(f'*{video_id}.*'))
        valid_files = [f for f in matching_files if f.suffix != '.part']
        
        # Separate merged files from format-coded files (e.g., .f251.webm)
        merged_files = [f for f in valid_files if '.f' not in f.name]
        format_coded_files = [f for f in valid_files if '.f' in f.name]
        
        if merged_files:
            # Prefer merged files
            for ext in ['.mp4', '.webm', '.mkv']:
                for f in merged_files:
                    if f.suffix == ext:
                        return f
            return merged_files[0]
        
        if format_coded_files:
            # Format-coded files indicate merge didn't happen - log warning
            logger.warning(f"Found unmerged format-coded files for video {video_id}. FFmpeg merge may have failed.")
            # Prefer video+audio combined formats, then video-only, then audio-only
            # Common video format codes are typically higher numbers
            for ext in ['.mp4', '.webm', '.mkv']:
                video_files = [f for f in format_coded_files if f.suffix == ext and not f.name.endswith(('.f251.webm', '.f250.webm', '.f249.webm'))]
                if video_files:
                    return video_files[0]
            return format_coded_files[0]
        
        return None
    
    def __init__(self):
        self.storage: StorageBackend = get_storage_backend()
        self.download_dir = self.storage.get_download_dir()
        
        cookies_status = check_cookies(settings.YT_DLP_COOKIES_FILE)
        if cookies_status.status == "valid":
            logger.info(f"Cookies valid: {cookies_status.message}")
        elif cookies_status.status == "expiring_soon":
            logger.warning(f"Cookies expiring soon: {cookies_status.message}")
        elif cookies_status.status == "expired":
            logger.error(f"Cookies EXPIRED: {cookies_status.message} - Refresh immediately!")
        elif cookies_status.status == "missing":
            logger.warning("No cookies file - YouTube may block downloads")
        else:
            logger.warning(f"Cookies status: {cookies_status.message}")
        
        storage_type = "S3" if settings.USE_S3 else "local"
        logger.info(f"Storage backend: {storage_type} ({self.download_dir})")
    
    def download(self, url: str) -> Dict:
        logger.info(f"Starting download for URL: {url}")
        
        try:
            output_template = "%(playlist_index|)svideo_%(id)s.%(ext)s"
            output_path = self.download_dir / output_template
            
            ydl_opts = {
                'format': (
                    'best[ext=mp4][height<=2160]/'
                    'bestvideo[ext=mp4][height<=2160]+bestaudio[ext=m4a]/'
                    'bestvideo[height<=2160]+bestaudio/'
                    'best[height<=2160]/'
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
                # Speed optimizations
                'concurrent_fragment_downloads': 8,  # Parallel fragment downloads for DASH/HLS (increase for more speed)
                'buffersize': 1024 * 16,  # Larger buffer for faster downloads
                # Sleep intervals (keep to avoid rate-limiting)
                'sleep_interval': 5,
                'max_sleep_interval': 15,
                'sleep_requests': 1,
            }
            
            if settings.cookies_file_exists:
                ydl_opts['cookiefile'] = str(settings.YT_DLP_COOKIES_FILE)
            
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
                            video_id = entry.get('id', '')
                            expected_filename = ydl.prepare_filename(entry)
                            filepath = self._find_downloaded_file(video_id, expected_filename)
                            
                            if filepath and filepath.exists():
                                file_url = self.storage.save_file(filepath, filepath.name)
                                filenames.append(filepath.name)
                                download_urls.append(file_url)
                    
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
                    video_id = info.get('id', '')
                    expected_filename = ydl.prepare_filename(info)
                    filepath = self._find_downloaded_file(video_id, expected_filename)
                    
                    if not filepath or not filepath.exists():
                        raise FileNotFoundError(f"Downloaded file not found for video ID {video_id}")
                    
                    logger.info(f"Download successful: {filepath.name}")
                    
                    file_url = self.storage.save_file(filepath, filepath.name)
                    
                    return {
                        'status': 'success',
                        'type': 'video',
                        'platform': info.get('extractor', ''),
                        'video_title': info.get('title', ''),
                        'filename': filepath.name,
                        'download_url': file_url
                    }
                
        except Exception as e:
            if "DownloadError" in type(e).__name__:
                logger.error(f"Download error: {str(e)}")
                raise Exception(f"Failed to download video: {str(e)}")
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise Exception(f"Error during download: {str(e)}")