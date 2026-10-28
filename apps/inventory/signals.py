from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.hospitals.models import Hospital

from .models import BloodInventory


@receiver(post_save, sender=Hospital)
def create_inventory_rows(sender, instance, created, **kwargs):
    """Every new hospital with a blood bank starts with all 8 type rows at zero."""
    if created and instance.has_blood_bank:
        BloodInventory.objects.ensure_for_hospital(instance)
