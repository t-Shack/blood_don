"""Local development settings. Points at the Neon `dev` branch, never SQLite."""
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')

SITE_URL = config('SITE_URL', default='http://localhost:8000')
