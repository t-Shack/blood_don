from django.db import models
from django.db.models import F
from django.utils import timezone

from apps.accounts.constants import BLOOD_GROUP_CHOICES, BLOOD_TYPES, RHESUS_CHOICES

_GROUP_ORDER = {'A': 0, 'B': 1, 'AB': 2, 'O': 3}
_RHESUS_ORDER = {'+': 0, '-': 1}


class BloodInventoryQuerySet(models.QuerySet):
    def ordered(self):
        """A+, A-, B+, B-, AB+, AB-, O+, O- — the order used in every grid."""
        return self.annotate(
            group_rank=models.Case(
                *[models.When(blood_group=g, then=models.Value(rank))
                  for g, rank in _GROUP_ORDER.items()],
                default=models.Value(9),
                output_field=models.IntegerField(),
            ),
            rhesus_rank=models.Case(
                *[models.When(rhesus_factor=r, then=models.Value(rank))
                  for r, rank in _RHESUS_ORDER.items()],
                default=models.Value(9),
                output_field=models.IntegerField(),
            ),
        ).order_by('group_rank', 'rhesus_rank')

    def shortages(self):
        return self.filter(available_units__lt=F('critical_threshold'))

    def for_hospital(self, hospital):
        return self.filter(hospital=hospital).ordered()


class BloodInventoryManager(models.Manager.from_queryset(BloodInventoryQuerySet)):
    def ensure_for_hospital(self, hospital, critical_threshold=5):
        """Create the 8 missing blood-type rows for a hospital, idempotently."""
        created = []
        for group, rhesus in BLOOD_TYPES:
            obj, was_created = self.get_or_create(
                hospital=hospital,
                blood_group=group,
                rhesus_factor=rhesus,
                defaults={'critical_threshold': critical_threshold},
            )
            if was_created:
                created.append(obj)
        return created


class BloodInventory(models.Model):
    """One row per blood group + Rh factor per hospital — eight rows each."""

    hospital = models.ForeignKey(
        'hospitals.Hospital', on_delete=models.CASCADE, related_name='inventory'
    )
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES)
    rhesus_factor = models.CharField(max_length=2, choices=RHESUS_CHOICES)
    available_units = models.IntegerField(default=0)
    critical_threshold = models.IntegerField(
        default=5,
        help_text='When available_units falls below this, the hospital is flagged in shortage',
    )
    last_updated = models.DateTimeField(auto_now=True)

    objects = BloodInventoryManager()

    class Meta:
        # PostgreSQL enforces this with a UNIQUE index.
        unique_together = ('hospital', 'blood_group', 'rhesus_factor')
        verbose_name_plural = 'blood inventory'
        ordering = ['hospital__name', 'blood_group', 'rhesus_factor']

    def __str__(self):
        return f'{self.hospital.name} - {self.full_blood_type}: {self.available_units} units'

    @property
    def full_blood_type(self):
        return f'{self.blood_group}{self.rhesus_factor}'

    @property
    def is_in_shortage(self):
        return self.available_units < self.critical_threshold

    @property
    def status(self):
        """`critical`, `low` or `sufficient` — drives the colour coding."""
        if self.available_units < self.critical_threshold:
            return 'critical'
        if self.available_units < self.critical_threshold * 2:
            return 'low'
        return 'sufficient'

    @property
    def status_label(self):
        return {
            'critical': 'Critical shortage',
            'low': 'Running low',
            'sufficient': 'Sufficient',
        }[self.status]

    @property
    def fill_percentage(self):
        """Units held as a share of a comfortable stock level (4x threshold)."""
        target = max(self.critical_threshold * 4, 1)
        return min(round(self.available_units / target * 100), 100)

    def add_units(self, units):
        type(self).objects.filter(pk=self.pk).update(
            available_units=F('available_units') + units,
            last_updated=timezone.now(),
        )
        self.refresh_from_db(fields=['available_units', 'last_updated'])
        return self.available_units

    def remove_units(self, units):
        """Atomic decrement, floored at zero. Returns units actually removed."""
        removed = min(units, self.available_units)
        if removed:
            type(self).objects.filter(pk=self.pk).update(
                available_units=F('available_units') - removed,
                last_updated=timezone.now(),
            )
            self.refresh_from_db(fields=['available_units', 'last_updated'])
        return removed

    def as_dict(self):
        return {
            'id': self.pk,
            'hospital_id': self.hospital_id,
            'blood_group': self.blood_group,
            'rhesus_factor': self.rhesus_factor,
            'blood_type': self.full_blood_type,
            'available_units': self.available_units,
            'critical_threshold': self.critical_threshold,
            'is_in_shortage': self.is_in_shortage,
            'status': self.status,
            'status_label': self.status_label,
            'fill_percentage': self.fill_percentage,
            'last_updated': self.last_updated.isoformat(),
        }
