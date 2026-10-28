"""Render production settings.

Which Neon branch the site uses (main or dev) is decided only by DATABASE_URL,
not by this file. Keep DJANGO_SETTINGS_MODULE=bdmis.settings.production on
Render either way.
"""
import os
from urllib.parse import urlparse

from .base import *  # noqa: F401,F403


def _bare_host(value):
    """Turn 'https://site.onrender.com/' into 'site.onrender.com'.

    Django matches ALLOWED_HOSTS against the bare hostname, so a pasted URL
    would otherwise reject every request with 400 Bad Request.
    """
    value = value.strip()
    if '://' in value:
        value = urlparse(value).netloc
    return value.rstrip('/')


DEBUG = False

ALLOWED_HOSTS = [
    _bare_host(h) for h in config('ALLOWED_HOSTS', default='', cast=Csv()) if h.strip()
]
# Render sets this to the service's own *.onrender.com hostname.
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # read by JS for AJAX POSTs
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'

# Origins need a scheme; accept bare hostnames too and assume https.
CSRF_TRUSTED_ORIGINS = [
    o.strip().rstrip('/') if '://' in o else f'https://{o.strip()}'
    for o in config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv()) if o.strip()
] or [f'https://{h}' for h in ALLOWED_HOSTS]

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
