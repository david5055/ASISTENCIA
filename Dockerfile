FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONUTF8=1
ENV HEADLESS=true

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m playwright install --with-deps chromium

COPY . .

CMD gunicorn --workers 1 --threads 4 --timeout 300 --bind 0.0.0.0:${PORT:-8080} app:app