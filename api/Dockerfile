# API de rossospeakeasy.com — servicio rosso-web-api en Cloud Run (proyecto motor-facturas).
FROM python:3.12-slim
ENV TZ=America/Mexico_City PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home --uid 1000 api && chown -R api:api /app
USER api
CMD exec gunicorn --bind :$PORT --workers 1 --threads 4 --timeout 600 app:app
