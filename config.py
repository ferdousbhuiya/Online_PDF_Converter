import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'pdfmaster-secret-key-2026')
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size
    
    ALLOWED_EXTENSIONS = {
        'pdf': ['pdf'],
        'word': ['doc', 'docx'],
        'excel': ['xls', 'xlsx'],
        'powerpoint': ['ppt', 'pptx'],
        'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
        'html': ['html', 'htm']
    }
    
    # Auto-cleanup files older than 30 minutes
    CLEANUP_INTERVAL = 1800