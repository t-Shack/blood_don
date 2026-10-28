from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DonorProfile, User


@receiver(post_save, sender=User)
def create_donor_profile(sender, instance, created, **kwargs):
    """Give every donor account a profile the moment it is created."""
    if created and instance.role == User.ROLE_DONOR:
        DonorProfile.objects.get_or_create(user=instance)
