from django.conf import settings
from django.db import models, transaction

from apps.inventory.models import BloodInventory


class DonationRecordQuerySet(models.QuerySet):
    def for_user(self, user):
        """Donors see their own donations; staff their hospital's; admins all."""
        if user.is_administrator:
            return self
        if user.is_medical_staff:
            if user.hospital_id:
                return self.filter(hospital_id=user.hospital_id)
            return self.filter(recorded_by=user)
        return self.filter(donor__user=user)


class DonationRecord(models.Model):
    donor = models.ForeignKey(
        'accounts.DonorProfile', on_delete=models.CASCADE, related_name='donations'
    )
    hospital = models.ForeignKey('hospitals.Hospital', on_delete=models.CASCADE)
    blood_request = models.ForeignKey(
        'bloodrequests.BloodRequest', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='donations',
    )
    donation_date = models.DateField()
    units_donated = models.IntegerField(default=1)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = DonationRecordQuerySet.as_manager()

    class Meta:
        ordering = ['-donation_date', '-created_at']
        indexes = [models.Index(fields=['donation_date'])]

    def __str__(self):
        return (
            f'{self.donor.user.get_full_name()} - {self.units_donated} unit(s) '
            f'{self.donor.full_blood_type} on {self.donation_date}'
        )

    @property
    def blood_type(self):
        return self.donor.full_blood_type

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        with transaction.atomic():
            super().save(*args, **kwargs)
            if not is_new:
                return

            donor = self.donor
            if not donor.last_donation_date or self.donation_date > donor.last_donation_date:
                donor.last_donation_date = self.donation_date
                donor.save(update_fields=['last_donation_date'])
            donor.update_eligibility()

            inventory, _ = BloodInventory.objects.get_or_create(
                hospital=self.hospital,
                blood_group=donor.blood_group,
                rhesus_factor=donor.rhesus_factor,
            )
            inventory.add_units(self.units_donated)

            # A donation logged against an open request counts towards it.
            if self.blood_request and self.blood_request.is_open:
                self.blood_request.try_fulfil_from_stock(self.units_donated)
