from django.contrib import admin

from .models import DonationCriteria, SiteStatistic


@admin.register(DonationCriteria)
class DonationCriteriaAdmin(admin.ModelAdmin):
    list_display = ['title', 'order', 'is_active', 'updated_at']
    list_editable = ['order', 'is_active']
    search_fields = ['title', 'content']


@admin.register(SiteStatistic)
class SiteStatisticAdmin(admin.ModelAdmin):
    list_display = ['key', 'label', 'value', 'updated_at']
