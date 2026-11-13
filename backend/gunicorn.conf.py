"""Gunicorn settings for production (docker-compose.prod.yml).

Sync workers + threads: the API is short DB-bound requests, and every write
holds row locks only inside one transaction. Tune with env vars on the VPS.
"""

import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", "4"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
worker_class = "gthread"
# Stay well under Cloudflare's 100 s origin timeout.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
graceful_timeout = 30
keepalive = 5
# Recycle workers now and then to cap memory growth (0 disables).
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "2000"))
max_requests_jitter = max_requests // 10
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOGLEVEL", "info")
