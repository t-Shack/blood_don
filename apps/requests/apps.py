from django.apps import AppConfig


class RequestsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.requests'
    label = 'bloodrequests'
    verbose_name = 'Blood requests'
