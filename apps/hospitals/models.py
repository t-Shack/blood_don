from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class HospitalQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def with_blood_bank(self):
        return self.filter(has_blood_bank=True)


class Hospital(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    has_blood_bank = models.BooleanField(default=True)
    blood_bank_capacity = models.IntegerField(
        default=0, help_text='Maximum blood units the blood bank can store'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = HospitalQuerySet.as_manager()

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['city']),
            models.Index(fields=['state']),
        ]

    def __str__(self):
        return f'{self.name} - {self.city}'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f'{self.name}-{self.city}')[:270]
            slug, counter = base, 2
            while Hospital.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('hospitals:detail', args=[self.pk])

    @property
    def total_units(self):
        return sum(item.available_units for item in self.inventory.all())

    @property
    def capacity_percentage(self):
        if not self.blood_bank_capacity:
            return 0
        return min(round(self.total_units / self.blood_bank_capacity * 100), 100)

    def shortage_types(self):
        """Blood types currently below their critical threshold here."""
        return [item.full_blood_type for item in self.inventory.all() if item.is_in_shortage]

    @property
    def is_in_shortage(self):
        return any(item.is_in_shortage for item in self.inventory.all())
