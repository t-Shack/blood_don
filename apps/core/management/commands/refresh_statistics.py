"""Recompute the cached headline numbers shown on the landing page."""
from django.core.management.base import BaseCommand
from django.db.models import Sum

from apps.accounts.models import DonorProfile
from apps.core.models import SiteStatistic
from apps.donations.models import DonationRecord
from apps.hospitals.models import Hospital
from apps.inventory.models import BloodInventory


class Command(BaseCommand):
    help = 'Refresh the SiteStatistic rows used by the landing page.'

    def _say(self, message):
        if getattr(self, 'verbosity', 1) >= 1:
            self.stdout.write(message)

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        values = {
            'hospitals': ('Partner hospitals', Hospital.objects.active().count()),
            'donors': ('Registered donors',
                       DonorProfile.objects.filter(user__is_active=True).count()),
            'units_available': (
                'Units in stock',
                BloodInventory.objects.filter(hospital__is_active=True)
                .aggregate(total=Sum('available_units'))['total'] or 0,
            ),
            'donations': (
                'Units donated to date',
                DonationRecord.objects.aggregate(total=Sum('units_donated'))['total'] or 0,
            ),
        }
        for key, (label, value) in values.items():
            SiteStatistic.objects.update_or_create(
                key=key, defaults={'label': label, 'value': value}
            )
            self._say(f'  {label}: {value}')
        self._say(self.style.SUCCESS('Statistics refreshed.'))
