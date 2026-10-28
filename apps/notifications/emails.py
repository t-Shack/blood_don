"""HTML email helpers. Every message is rendered from a template, never inline."""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def absolute_url(view_name, *args):
    return f"{settings.SITE_URL.rstrip('/')}{reverse(view_name, args=args)}"


def send_html_email(subject, template, context, recipient_list):
    html_body = render_to_string(template, context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=strip_tags(html_body),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipient_list,
    )
    message.attach_alternative(html_body, 'text/html')
    message.send(fail_silently=False)
    return True


def send_welcome_email(user):
    """Best-effort welcome mail; registration must never fail because SMTP did."""
    try:
        send_html_email(
            subject='Welcome to BDMIS: you are now a registered donor',
            template='emails/welcome.html',
            context={
                'donor_name': user.get_full_name(),
                'dashboard_url': absolute_url('accounts:dashboard'),
                'criteria_url': absolute_url('core:criteria'),
                'hospitals_url': absolute_url('hospitals:list'),
            },
            recipient_list=[user.email],
        )
        return True
    except Exception:
        logger.exception('Welcome email failed for %s', user.email)
        return False
