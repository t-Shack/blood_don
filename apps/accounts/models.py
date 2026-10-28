from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .constants import BLOOD_GROUP_CHOICES, RHESUS_CHOICES, compatible_recipients_for
from .managers import UserManager

DONATION_INTERVAL_DAYS = getattr(settings, 'DONATION_INTERVAL_DAYS', 56)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model. `role` determines access level across the system."""

    ROLE_DONOR = 'donor'
    ROLE_STAFF = 'staff'
    ROLE_ADMIN = 'admin'
    ROLE_CHOICES = [
        (ROLE_DONOR, 'Donor'),
        (ROLE_STAFF, 'Medical Staff'),
        (ROLE_ADMIN, 'Administrator'),
    ]

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_DONOR)
    hospital = models.ForeignKey(
        'hospitals.Hospital',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_members',
        help_text='Hospital this medical staff member works at.',
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'role']

    class Meta:
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.username} <{self.email}>'

    def get_full_name(self):
        return self.full_name or self.username

    def get_short_name(self):
        return self.username

    @property
    def is_donor(self):
        return self.role == self.ROLE_DONOR

    @property
    def is_medical_staff(self):
        return self.role == self.ROLE_STAFF

    @property
    def is_administrator(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser


class DonorProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='donor_profile'
    )
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, default='O')
    rhesus_factor = models.CharField(max_length=2, choices=RHESUS_CHOICES, default='+')
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    last_donation_date = models.DateField(null=True, blank=True)
    is_eligible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return f'{self.user.get_full_name()} ({self.full_blood_type})'

    @property
    def full_blood_type(self):
        return f'{self.blood_group}{self.rhesus_factor}'

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def next_eligible_date(self):
        """Date the donor becomes eligible again (56 days after last donation)."""
        if self.last_donation_date:
            return self.last_donation_date + timedelta(days=DONATION_INTERVAL_DAYS)
        return None

    @property
    def days_until_eligible(self):
        next_date = self.next_eligible_date
        if not next_date:
            return 0
        return max((next_date - date.today()).days, 0)

    def compatible_recipient_types(self):
        """Recipient blood types this donor can give to."""
        return compatible_recipients_for(self.blood_group, self.rhesus_factor)

    def update_eligibility(self):
        if self.last_donation_date:
            eligible = (date.today() - self.last_donation_date).days >= DONATION_INTERVAL_DAYS
        else:
            eligible = True
        if eligible != self.is_eligible:
            self.is_eligible = eligible
            self.save(update_fields=['is_eligible'])
        return self.is_eligible


class LoginAttempt(models.Model):
    """Audit trail of authentication attempts, used for rate limiting reports."""

    email = models.CharField(max_length=254)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    successful = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-attempted_at']

    def __str__(self):
        outcome = 'success' if self.successful else 'failure'
        return f'{self.email} - {outcome} @ {self.attempted_at:%Y-%m-%d %H:%M}'
