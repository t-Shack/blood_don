import logging
import threading

from django.db import close_old_connections

from apps.accounts.models import DonorProfile

from .emails import absolute_url, send_html_email
from .models import Notification

logger = logging.getLogger(__name__)


def eligible_compatible_donors(blood_request):
    """Active, eligible donors whose blood type can serve this request."""
    compatible_types = blood_request.get_compatible_blood_groups()
    if not compatible_types:
        return []

    candidates = DonorProfile.objects.filter(
        blood_group__in={group for group, _ in compatible_types},
        rhesus_factor__in={rhesus for _, rhesus in compatible_types},
        is_eligible=True,
        user__is_active=True,
    ).select_related('user')

    return [
        donor for donor in candidates
        if (donor.blood_group, donor.rhesus_factor) in compatible_types
    ]


def dispatch_blood_request_notifications(blood_request):
    donors = eligible_compatible_donors(blood_request)
    sent = failed = 0

    subject = (
        f'[{blood_request.get_urgency_level_display().upper()}] '
        f'{blood_request.full_blood_type} blood needed at {blood_request.hospital.name}'
    )
    context_base = {
        'hospital_name': blood_request.hospital.name,
        'hospital_city': blood_request.hospital.city,
        'blood_type_needed': blood_request.full_blood_type,
        'urgency_level': blood_request.get_urgency_level_display(),
        'units_needed': blood_request.units_outstanding or blood_request.quantity_needed,
        'donate_url': absolute_url('accounts:dashboard'),
        'criteria_url': absolute_url('core:criteria'),
        'hospital_url': absolute_url('hospitals:detail', blood_request.hospital_id),
        'unsubscribe_note': (
            'You are receiving this because your blood type can help this patient. '
            'Alert preferences will be configurable from your dashboard in a future release.'
        ),
    }

    for donor in donors:
        try:
            send_html_email(
                subject=subject,
                template='emails/blood_request_alert.html',
                context={**context_base, 'donor_name': donor.user.get_full_name()},
                recipient_list=[donor.user.email],
            )
            Notification.objects.create(
                donor=donor,
                blood_request=blood_request,
                message=(
                    f'Alert sent for {blood_request.full_blood_type} at '
                    f'{blood_request.hospital.name}'
                ),
                status=Notification.STATUS_SENT,
            )
            sent += 1
        except Exception:
            logger.exception('Alert email failed for donor %s', donor.user.email)
            Notification.objects.create(
                donor=donor,
                blood_request=blood_request,
                message=(
                    f'Failed to send alert for {blood_request.full_blood_type} at '
                    f'{blood_request.hospital.name}'
                ),
                status=Notification.STATUS_FAILED,
            )
            failed += 1

    logger.info(
        'Blood request %s: alerted %s donor(s), %s failure(s)',
        blood_request.pk, sent, failed,
    )
    return sent, failed


def _run_in_thread(blood_request):
    try:
        dispatch_blood_request_notifications(blood_request)
    finally:
        # A thread gets its own DB connection; hand it back when finished.
        close_old_connections()


def dispatch_blood_request_notifications_async(blood_request):
    """Fire-and-forget dispatch on a daemon thread."""
    thread = threading.Thread(
        target=_run_in_thread, args=(blood_request,),
        name=f'bdmis-alerts-{blood_request.pk}', daemon=True,
    )
    thread.start()
    return thread
