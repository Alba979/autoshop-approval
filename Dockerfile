FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p instance/uploads/diagnostic_photos

ENV FLASK_APP=wsgi.py \
    FLASK_ENV=production \
    PORT=8000

EXPOSE 8000

# 2 workers is plenty for a single-shop deployment; raise --workers if the
# shop runs multiple bays hitting the dashboard concurrently.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "wsgi:app"]
