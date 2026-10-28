from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['donor', 'blood_request', 'status', 'is_read', 'sent_at']
    list_filter = ['status', 'is_read']
    search_fields = ['donor__user__email', 'message']
    readonly_fields = ['sent_at']
