FROM python:3.12-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir .
EXPOSE 8000
