FROM python:3.11-slim

# Install WeasyPrint + pytesseract native dependencies + Arabic fonts
# All packages listed explicitly per specification (§4)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu \
    fonts-noto \
    fonts-noto-cjk \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

# Refresh font cache so WeasyPrint can discover Noto Sans Arabic / DejaVu
RUN fc-cache -f -v

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
