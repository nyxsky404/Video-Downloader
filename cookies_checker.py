from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
import yt_dlp


@dataclass
class CookiesStatus:
    exists: bool
    status: str
    message: str
    cookie_count: int = 0
    expires_at: str = ""
    days_until_expiry: int = 0
    can_download: bool = False
    
    def to_dict(self) -> dict:
        return {
            "exists": self.exists,
            "status": self.status,
            "message": self.message,
            "cookie_count": self.cookie_count,
            "expires_at": self.expires_at,
            "days_until_expiry": self.days_until_expiry,
            "can_download": self.can_download,
        }


def test_cookies_with_youtube(cookies_path: Path) -> tuple[bool, str]:
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'cookiefile': str(cookies_path),
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", download=False)
            if info:
                return True, "YouTube access confirmed"
            return False, "Could not extract video info"
    except Exception as e:
        error_msg = str(e).lower()
        auth_errors = ["sign in", "bot", "cookies are no longer valid", "confirm you", "not a bot"]
        if any(err in error_msg for err in auth_errors):
            return False, "Cookies rejected by YouTube"
        return True, "YouTube accessible (non-auth error ignored)"


def check_cookies(cookies_path: Path, test_with_youtube: bool = False) -> CookiesStatus:
    path_str = str(cookies_path) if cookies_path else ""
    if not path_str or path_str == ".":
        return CookiesStatus(
            exists=False,
            status="not_configured",
            message="Cookies file path not configured",
            can_download=False
        )
    
    if not cookies_path.exists():
        return CookiesStatus(
            exists=False,
            status="missing",
            message="Cookies file not found",
            can_download=False
        )
    
    try:
        now = datetime.now()
        auth_cookie_expiry = None
        cookie_count = 0
        has_auth_cookies = False
        
        youtube_auth_cookies = {'SID', 'HSID', 'SSID', 'APISID', 'SAPISID', 'SIDCC', 'LOGIN_INFO'}
        
        with open(cookies_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 7:
                    cookie_count += 1
                    cookie_name = parts[5]
                    if cookie_name in youtube_auth_cookies:
                        has_auth_cookies = True
                        try:
                            expiry_ts = int(parts[4])
                            if expiry_ts > 0:
                                expiry = datetime.fromtimestamp(expiry_ts)
                                if auth_cookie_expiry is None or expiry < auth_cookie_expiry:
                                    auth_cookie_expiry = expiry
                        except (ValueError, OSError):
                            pass
        
        if cookie_count == 0:
            return CookiesStatus(
                exists=True,
                status="empty",
                message="Cookies file is empty",
                can_download=False
            )
        
        can_download = None
        youtube_test_msg = ""
        
        if test_with_youtube and has_auth_cookies:
            can_download, youtube_test_msg = test_cookies_with_youtube(cookies_path)
        
        if not has_auth_cookies:
            return CookiesStatus(
                exists=True,
                status="valid" if not test_with_youtube else ("valid" if can_download else "invalid"),
                cookie_count=cookie_count,
                message=f"Found {cookie_count} cookies" + (f" - {youtube_test_msg}" if test_with_youtube else ""),
                can_download=can_download if test_with_youtube else True
            )
        
        if auth_cookie_expiry is None:
            return CookiesStatus(
                exists=True,
                status="valid" if not test_with_youtube else ("valid" if can_download else "invalid"),
                cookie_count=cookie_count,
                message=f"Found {cookie_count} cookies with auth tokens" + (f" - {youtube_test_msg}" if test_with_youtube else ""),
                can_download=can_download if test_with_youtube else True
            )
        
        if auth_cookie_expiry < now:
            return CookiesStatus(
                exists=True,
                status="expired",
                cookie_count=cookie_count,
                expires_at=auth_cookie_expiry.isoformat(),
                message=f"Auth cookies expired on {auth_cookie_expiry.strftime('%Y-%m-%d')}",
                can_download=False
            )
        
        days_until_expiry = (auth_cookie_expiry - now).days
        
        if days_until_expiry <= 7:
            return CookiesStatus(
                exists=True,
                status="expiring_soon",
                cookie_count=cookie_count,
                expires_at=auth_cookie_expiry.isoformat(),
                days_until_expiry=days_until_expiry,
                message=f"Auth cookies expire in {days_until_expiry} days - refresh soon" + (f" - {youtube_test_msg}" if test_with_youtube else ""),
                can_download=can_download if test_with_youtube else True
            )
        
        return CookiesStatus(
            exists=True,
            status="valid" if not test_with_youtube else ("valid" if can_download else "invalid"),
            cookie_count=cookie_count,
            expires_at=auth_cookie_expiry.isoformat(),
            days_until_expiry=days_until_expiry,
            message=f"Cookies valid for {days_until_expiry} more days" + (f" - {youtube_test_msg}" if test_with_youtube else ""),
            can_download=can_download if test_with_youtube else True
        )
        
    except Exception as e:
        return CookiesStatus(
            exists=True,
            status="error",
            message=f"Error reading cookies: {str(e)}",
            can_download=False
        )
