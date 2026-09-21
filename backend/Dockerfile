FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY backend ./backend
COPY migrations ./migrations
RUN pip install --no-cache-dir .
EXPOSE 8000

