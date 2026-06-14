import os
from dotenv import load_dotenv

# Load env file if it exists
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'mail_sarthi_default_fallback_secret_key_9876543210'
    
    # CSRF Trusted Origins (needed for HTTPS proxying)
    WTF_CSRF_TRUSTED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000').split(',')
    
    # SMTP Server Settings (defaults to Gmail)
    SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    
    # Database
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        
        # Safely quote password special characters (e.g. %, &) to prevent SQLAlchemy parsing errors
        from urllib.parse import urlparse, urlunparse, quote_plus
        try:
            parsed = urlparse(db_url)
            if parsed.password:
                password_quoted = quote_plus(parsed.password)
                user_part = parsed.username or ''
                host_part = parsed.hostname or ''
                port_part = f":{parsed.port}" if parsed.port else ''
                netloc = f"{user_part}:{password_quoted}@{host_part}{port_part}"
                parsed = parsed._replace(netloc=netloc)
                db_url = urlunparse(parsed)
        except Exception as e:
            print(f"Warning: Could not format database URL: {e}")

    SQLALCHEMY_DATABASE_URI = db_url or f"sqlite:///{os.path.join(BASE_DIR, 'database', 'database.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload Settings
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max limit for CSV files
    
    # Log files
    LOG_DIR = os.path.join(BASE_DIR, 'logs')
    SENT_LOG = os.path.join(LOG_DIR, 'sent.log')
    FAILED_LOG = os.path.join(LOG_DIR, 'failed.log')
    ERROR_LOG = os.path.join(LOG_DIR, 'error.log')

# Create necessary directories
for directory in [
    os.path.join(BASE_DIR, 'database'),
    os.path.join(BASE_DIR, 'uploads'),
    os.path.join(BASE_DIR, 'logs')
]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Force resolve SMTP_HOST to IPv4 to bypass Render's broken IPv6 routing
import socket
original_getaddrinfo = socket.getaddrinfo
def custom_getaddrinfo(host, port, family=0, *args, **kwargs):
    if host == 'smtp.gmail.com' or host == Config.SMTP_HOST:
        return original_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)
    return original_getaddrinfo(host, port, family, *args, **kwargs)
socket.getaddrinfo = custom_getaddrinfo
