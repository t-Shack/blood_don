from django.contrib import admin

from .models import Hospital


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'state', 'has_blood_bank',
                    'blood_bank_capacity', 'is_active']
    list_filter = ['state', 'city', 'has_blood_bank', 'is_active']
    search_fields = ['name', 'city', 'state', 'address']
    prepopulated_fields = {'slug': ('name',)}
