import os
from dotenv import load_dotenv

# Load env file if it exists
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_for_email_automation_system_1298371982')
    
    # Database
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
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
