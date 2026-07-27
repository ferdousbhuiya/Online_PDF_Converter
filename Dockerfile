FROM python:3.11

# Install LibreOffice headless
RUN apt-get update && apt-get install -y \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Copy requirements first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Render sets PORT env var
EXPOSE 10000
CMD gunicorn app:app --workers 1 --timeout 180 --bind 0.0.0.0:$PORT
