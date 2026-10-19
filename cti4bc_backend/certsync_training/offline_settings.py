"""Offline tests only: synthetic settings, SQLite, no .env or services."""
SECRET_KEY = "offline-tests-only-not-a-deployment-secret"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "rest_framework", "organizations", "event", "playbook", "event_files", "public_key",
    "strategies", "anonattributes", "misp_servers", "ip_reputation", "certsync_training"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
MIDDLEWARE = ["certsync_training.middleware.TrainingBoundaryMiddleware", "django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "certsync_training.offline_urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
MEDIA_ROOT = "/tmp/certsync-training-test-media"
MEDIA_URL = "/media/"
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ["certsync_training.auth.TrainingJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"]}
SIMPLE_JWT = {"TOKEN_REFRESH_SERIALIZER": "certsync_training.auth.TrainingRefreshSerializer"}
CERTSYNC_TRAINING_ENABLED = True
CTI4BC_SSO_SECRET = "synthetic-cti-training-secret-" * 3
CERTSYNC_PLATFORM_MISP_URL = "https://misp.example"
CERTSYNC_FRAME_ANCESTORS = "https://platform.example"
TRAINING_ORG_PREFIX = "TRAIN-"
TRAINING_ORG_COUNT = 25
KAFKA_SERVER = "unused.invalid:9092"
KAFKA_USERNAME = "offline"
KAFKA_PASSWORD = "offline"
CTI_REMOTE_TOPIC = "CTI4BC.remote_incident"
RISK_TOPIC = "RISK4BC.risk_profile"
FRONTEND_URL = "https://cti.example"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
