from django.contrib import admin

from .models import BloodRequest


@admin.register(BloodRequest)
class BloodRequestAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'hospital', 'urgency_level', 'status',
                    'quantity_needed', 'units_fulfilled', 'created_at']
    list_filter = ['status', 'urgency_level', 'hospital', 'blood_group']
    search_fields = ['patient_name', 'hospital__name', 'requested_by__email']
    readonly_fields = ['created_at', 'updated_at']
