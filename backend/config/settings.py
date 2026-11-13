import os
import sys
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() in ("1", "true", "yes")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false")
    SECRET_KEY = "dev-insecure-change-me"
elif not DEBUG and (len(SECRET_KEY) < 32 or "change-me" in SECRET_KEY.lower()):
    raise RuntimeError(
        "DJANGO_SECRET_KEY is a placeholder or shorter than 32 characters; "
        "set a long random key when DJANGO_DEBUG is false"
    )
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "django_q",
    "apps.core",
    "apps.accounts",
    "apps.rbac",
    "apps.audit",
    "apps.lab",
    "apps.banking",
    "apps.customers",
    "apps.ledger",
    "apps.products",
    "apps.reports",
    "apps.exams",
]

MIDDLEWARE = [
    "apps.core.middleware.ProxyTrustMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default="postgres://banklab:banklab@localhost:5432/banklab",
        conn_max_age=int(os.environ.get("DJANGO_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "Africa/Mogadishu")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_USE_FINDERS = DEBUG  # dev: serve admin assets without collectstatic
# Hashed + compressed static files (admin assets) served by WhiteNoise in production. Dev and
# the test-suite use the plain storage so nothing needs `collectstatic`.
_TESTING = "pytest" in sys.modules
if not DEBUG and not _TESTING:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
CORS_ALLOW_CREDENTIALS = True

AUTH_USER_MODEL = "accounts.User"
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "http://localhost:3000")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

Q_CLUSTER = {
    "name": "banklab",
    "orm": "default",
    "workers": 2,
    "timeout": 60,
    "retry": 120,
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

# Uploaded customer files (photos, signatures, ID documents). Never served statically:
# they are only streamed by the customers API after a bank/visibility check.
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media")))
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# --- Trusted client IP (login throttle + audit log) ---------------------------------------
# Name of the META key a trusted reverse proxy sets, e.g. HTTP_CF_CONNECTING_IP (Cloudflare) or
# HTTP_X_REAL_IP (nginx). Empty = use REMOTE_ADDR. See apps/core/net.py.
CLIENT_IP_HEADER = os.environ.get("CLIENT_IP_HEADER", "").strip()
# Optional shared secret the reverse proxy sends as X-BankLab-Proxy. When set, CLIENT_IP_HEADER and
# X-Forwarded-Proto are ignored on requests without it (sibling containers on a shared network).
PROXY_SHARED_SECRET = os.environ.get("PROXY_SHARED_SECRET", "").strip()


# --- Production security (inactive when DJANGO_DEBUG=true) --------------------------------
def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


if not DEBUG:
    # Behind nginx/Cloudflare the app sees plain HTTP; trust X-Forwarded-For-Proto only when the
    # proxy is known to overwrite it.
    if env_bool("DJANGO_TRUST_PROXY_PROTO"):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Leave off while Cloudflare terminates TLS ("Flexible" mode talks plain HTTP to the origin,
    # so a Django redirect would loop). Cloudflare's "Always Use HTTPS" does the redirect.
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT")
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS")
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_HSTS_PRELOAD")
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

# --- Logging: stdout only, no request bodies or secrets ------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}
