"""WSGI entrypoint used by gunicorn on Render."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bdmis.settings.production')

application = get_wsgi_application()
