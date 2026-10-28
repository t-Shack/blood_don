from django.conf import settings
from django.db import models, transaction
from django.urls import reverse

from apps.accounts.constants import (
    BLOOD_GROUP_CHOICES,
    RHESUS_CHOICES,
    compatible_donors_for,
)


class BloodRequestQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status=BloodRequest.STATUS_PENDING)

    def for_user(self, user):
        """Admins see everything; staff see their hospital's requests."""
        if user.is_administrator:
            return self
        if user.is_medical_staff:
            if user.hospital_id:
                return self.filter(
                    models.Q(hospital_id=user.hospital_id) | models.Q(requested_by=user)
                )
            return self.filter(requested_by=user)
        return self.none()


class BloodRequest(models.Model):
    URGENCY_LOW = 'low'
    URGENCY_MEDIUM = 'medium'
    URGENCY_CRITICAL = 'critical'
    URGENCY_CHOICES = [
        (URGENCY_LOW, 'Low'),
        (URGENCY_MEDIUM, 'Medium'),
        (URGENCY_CRITICAL, 'Critical'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_FULFILLED = 'fulfilled'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_FULFILLED, 'Fulfilled'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    hospital = models.ForeignKey('hospitals.Hospital', on_delete=models.CASCADE)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blood_requests'
    )
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES)
    rhesus_factor = models.CharField(max_length=2, choices=RHESUS_CHOICES)
    quantity_needed = models.IntegerField()
    units_fulfilled = models.IntegerField(default=0)
    urgency_level = models.CharField(
        max_length=10, choices=URGENCY_CHOICES, default=URGENCY_MEDIUM
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDING)
    patient_name = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BloodRequestQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['blood_group', 'rhesus_factor']),
        ]

    def __str__(self):
        return f'{self.full_blood_type} x{self.quantity_needed} @ {self.hospital.name}'

    def get_absolute_url(self):
        return reverse('requests:detail', args=[self.pk])

    @property
    def full_blood_type(self):
        return f'{self.blood_group}{self.rhesus_factor}'

    @property
    def units_outstanding(self):
        return max(self.quantity_needed - self.units_fulfilled, 0)

    @property
    def is_open(self):
        return self.status == self.STATUS_PENDING

    def get_compatible_blood_groups(self):
        return compatible_donors_for(self.blood_group, self.rhesus_factor)

    def matching_inventory(self):
        """This hospital's stock row for the exact type requested."""
        from apps.inventory.models import BloodInventory
        return BloodInventory.objects.filter(
            hospital=self.hospital,
            blood_group=self.blood_group,
            rhesus_factor=self.rhesus_factor,
        ).first()

    @transaction.atomic
    def try_fulfil_from_stock(self, units=None):
        inventory = self.matching_inventory()
        if inventory is None:
            return 0
        wanted = self.units_outstanding if units is None else min(units, self.units_outstanding)
        if wanted <= 0:
            return 0
        taken = inventory.remove_units(wanted)
        if taken:
            self.units_fulfilled += taken
            if self.units_outstanding == 0:
                self.status = self.STATUS_FULFILLED
            self.save(update_fields=['units_fulfilled', 'status', 'updated_at'])
        return taken

    def cancel(self):
        self.status = self.STATUS_CANCELLED
        self.save(update_fields=['status', 'updated_at'])
