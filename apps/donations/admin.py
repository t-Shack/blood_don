from django.contrib import admin

from .models import DonationRecord


@admin.register(DonationRecord)
class DonationRecordAdmin(admin.ModelAdmin):
    list_display = ['donor', 'blood_type', 'hospital', 'units_donated',
                    'donation_date', 'recorded_by']
    list_filter = ['hospital', 'donation_date']
    search_fields = ['donor__user__email', 'donor__user__full_name', 'hospital__name']
    date_hierarchy = 'donation_date'
