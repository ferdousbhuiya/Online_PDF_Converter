FROM ghcr.io/ferdousbhuiya/pdf-doc-tools-base:py311

WORKDIR /app

# Application-specific Python dependencies remain in the app layer so normal
# code deployments do not rebuild LibreOffice, OCR, Ghostscript, fonts or LaTeX.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=10000
EXPOSE 10000

CMD ["sh", "-c", "python cleanup_worker.py & exec gunicorn patched_app:app --workers 1 --timeout 180 --bind 0.0.0.0:${PORT}"]
