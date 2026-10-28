from django.db.models import Count, Sum
from django.shortcuts import render

from apps.accounts.constants import BLOOD_TYPES, COMPATIBILITY
from apps.accounts.models import DonorProfile
from apps.donations.models import DonationRecord
from apps.hospitals.models import Hospital
from apps.inventory.models import BloodInventory

from .models import DonationCriteria


def home(request):
    """Public landing page. Every number here is live, nothing hardcoded."""
    shortages = (
        BloodInventory.objects.shortages()
        .filter(hospital__is_active=True)
        .select_related('hospital')
        .ordered()
    )
    stats = {
        'hospitals': Hospital.objects.active().with_blood_bank().count(),
        'donors': DonorProfile.objects.filter(user__is_active=True).count(),
        'units_available': BloodInventory.objects.filter(hospital__is_active=True)
                                                 .aggregate(total=Sum('available_units'))['total'] or 0,
        'donations': DonationRecord.objects.aggregate(total=Sum('units_donated'))['total'] or 0,
    }
    context = {
        'stats': stats,
        'shortages': shortages[:8],
        'shortage_total': shortages.count(),
        'shortage_hospitals': shortages.values('hospital').distinct().count(),
        'featured_hospitals': Hospital.objects.active().with_blood_bank()
                                      .annotate(types=Count('inventory'))[:3],
        'criteria_preview': DonationCriteria.objects.filter(is_active=True)[:3],
    }
    return render(request, 'core/home.html', context)


def criteria(request):
    """Health donation criteria, managed by admins through the CMS model."""
    return render(request, 'core/criteria.html', {
        'criteria_list': DonationCriteria.objects.filter(is_active=True),
    })


def about(request):
    labels = [f'{group}{rhesus}' for group, rhesus in BLOOD_TYPES]
    compatibility_rows = [
        {
            'donor': f'{group}{rhesus}',
            'cells': [
                {'recipient': label, 'ok': (group, rhesus) in COMPATIBILITY[recipient]}
                for recipient, label in zip(BLOOD_TYPES, labels)
            ],
        }
        for group, rhesus in BLOOD_TYPES
    ]
    return render(request, 'core/about.html', {
        'blood_type_labels': labels,
        'compatibility_rows': compatibility_rows,
    })


def error_403(request, exception=None):
    return render(request, 'core/errors/403.html', status=403)


def error_404(request, exception=None):
    return render(request, 'core/errors/404.html', status=404)


def error_500(request):
    return render(request, 'core/errors/500.html', status=500)
