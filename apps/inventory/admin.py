from django.contrib import admin

from .models import BloodInventory


@admin.register(BloodInventory)
class BloodInventoryAdmin(admin.ModelAdmin):
    list_display = ['hospital', 'full_blood_type', 'available_units',
                    'critical_threshold', 'is_in_shortage', 'last_updated']
    list_filter = ['hospital', 'blood_group', 'rhesus_factor']
    search_fields = ['hospital__name']
    list_editable = ['available_units', 'critical_threshold']

    @admin.display(boolean=True, description='In shortage')
    def is_in_shortage(self, obj):
        return obj.is_in_shortage
