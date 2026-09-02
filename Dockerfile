FROM python:3.11

# System tools required by document conversion, PDF rendering, OCR and compression
RUN apt-get update && apt-get install -y \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    poppler-utils \
    tesseract-ocr \
    ghostscript \
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render provides PORT. Coolify can provide it too; 10000 is the fallback.
ENV PORT=10000
EXPOSE 10000

# Run nested temp-file cleanup alongside Gunicorn.
CMD ["sh", "-c", "python cleanup_worker.py & exec gunicorn patched_app:app --workers 1 --timeout 180 --bind 0.0.0.0:${PORT}"]
