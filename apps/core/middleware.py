from django.http import HttpResponse


class HealthCheckMiddleware:
    """Answer Render's health check at /healthz before anything else runs.

    It sits first in MIDDLEWARE so the check skips the hostname check, the
    HTTPS redirect and the database: a slow Neon wake-up or an internal Host
    header cannot make Render mark the deploy as failed.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ('/healthz', '/healthz/'):
            return HttpResponse('ok', content_type='text/plain')
        return self.get_response(request)
