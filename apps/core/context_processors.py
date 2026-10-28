from django.conf import settings


def site_context(request):
    """Values every template needs: branding, poll interval, unread badge."""
    unread = 0
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated and user.is_donor:
        profile = getattr(user, 'donor_profile', None)
        if profile is not None:
            unread = profile.notifications.filter(is_read=False).count()

    return {
        'SITE_NAME': 'BDMIS',
        'SITE_TAGLINE': 'Blood Donor Management Information System',
        'INVENTORY_POLL_INTERVAL_MS': settings.INVENTORY_POLL_INTERVAL_MS,
        'INVENTORY_POLL_INTERVAL_SECONDS': settings.INVENTORY_POLL_INTERVAL_MS // 1000,
        'DONATION_INTERVAL_DAYS': settings.DONATION_INTERVAL_DAYS,
        'unread_notification_count': unread,
    }
