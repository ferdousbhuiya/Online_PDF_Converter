import os
import secrets


class Config:
    # Prefer an explicit production secret. If none is configured, generate a
    # strong per-process value instead of shipping a predictable hard-coded key.
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')

    # Each individual file is limited to 100MB by the hardened conversion route.
    # The request-level ceiling is larger so multi-file tools such as Merge PDF
    # are not incorrectly blocked when several valid files are uploaded together.
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_REQUEST_BYTES', str(300 * 1024 * 1024)))

    ALLOWED_EXTENSIONS = {
        'pdf': ['pdf'],
        'word': ['doc', 'docx'],
        'excel': ['xls', 'xlsx'],
        'powerpoint': ['ppt', 'pptx'],
        'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
        'html': ['html', 'htm']
    }

    # Auto-cleanup files older than 30 minutes
    CLEANUP_INTERVAL = int(os.environ.get('FILE_RETENTION_SECONDS', '1800'))
