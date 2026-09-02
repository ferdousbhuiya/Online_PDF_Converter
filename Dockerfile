FROM python:3.11

# System tools required by document conversion, PDF rendering, OCR and compression.
# Carlito/Caladea improve Microsoft Office layout fidelity (Calibri/Cambria substitutes).
# Noto/Lohit Bengali provide reliable Bengali glyph coverage for LibreOffice conversions.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-spa \
    tesseract-ocr-ita \
    ghostscript \
    fontconfig \
    fonts-liberation \
    fonts-dejavu-core \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    fonts-noto-core \
    fonts-lohit-beng-bengali \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=10000
EXPOSE 10000

CMD ["sh", "-c", "python cleanup_worker.py & exec gunicorn patched_app:app --workers 1 --timeout 180 --bind 0.0.0.0:${PORT}"]
