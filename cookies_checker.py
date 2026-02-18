from pathlib import Path
from datetime import datetime
from dataclasses import dataclass


@dataclass
class CookiesStatus:
    exists: bool
    status: str
    message: str
    cookie_count: int = 0
    expires_at: str = ""
    days_until_expiry: int = 0
    
    def to_dict(self) -> dict:
        return {
            "exists": self.exists,
            "status": self.status,
            "message": self.message,
            "cookie_count": self.cookie_count,
            "expires_at": self.expires_at,
            "days_until_expiry": self.days_until_expiry,
        }


def check_cookies(cookies_path: Path) -> CookiesStatus:
    path_str = str(cookies_path) if cookies_path else ""
    if not path_str or path_str == ".":
        return CookiesStatus(
            exists=False,
            status="not_configured",
            message="Cookies file path not configured"
        )
    
    if not cookies_path.exists():
        return CookiesStatus(
            exists=False,
            status="missing",
            message="Cookies file not found"
        )
    
    try:
        now = datetime.now()
        earliest_expiry = None
        cookie_count = 0
        
        with open(cookies_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 7:
                    cookie_count += 1
                    try:
                        expiry_ts = int(parts[4])
                        if expiry_ts > 0:
                            expiry = datetime.fromtimestamp(expiry_ts)
                            if earliest_expiry is None or expiry < earliest_expiry:
                                earliest_expiry = expiry
                    except (ValueError, OSError):
                        pass
        
        if cookie_count == 0:
            return CookiesStatus(
                exists=True,
                status="empty",
                message="Cookies file is empty"
            )
        
        if earliest_expiry is None:
            return CookiesStatus(
                exists=True,
                status="unknown",
                cookie_count=cookie_count,
                message="Could not determine cookie expiration"
            )
        
        if earliest_expiry < now:
            return CookiesStatus(
                exists=True,
                status="expired",
                cookie_count=cookie_count,
                expires_at=earliest_expiry.isoformat(),
                message=f"Cookies expired on {earliest_expiry.strftime('%Y-%m-%d')}"
            )
        
        days_until_expiry = (earliest_expiry - now).days
        
        if days_until_expiry <= 7:
            return CookiesStatus(
                exists=True,
                status="expiring_soon",
                cookie_count=cookie_count,
                expires_at=earliest_expiry.isoformat(),
                days_until_expiry=days_until_expiry,
                message=f"Cookies expire in {days_until_expiry} days - refresh soon"
            )
        
        return CookiesStatus(
            exists=True,
            status="valid",
            cookie_count=cookie_count,
            expires_at=earliest_expiry.isoformat(),
            days_until_expiry=days_until_expiry,
            message=f"Cookies valid for {days_until_expiry} more days"
        )
        
    except Exception as e:
        return CookiesStatus(
            exists=True,
            status="error",
            message=f"Error reading cookies: {str(e)}"
        )
