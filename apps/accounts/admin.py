from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import DonorProfile, LoginAttempt, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['-date_joined']
    list_display = ['email', 'username', 'full_name', 'role', 'hospital', 'is_active']
    list_filter = ['role', 'is_active', 'is_staff']
    search_fields = ['email', 'username', 'full_name']
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal', {'fields': ('full_name',)}),
        ('Role', {'fields': ('role', 'hospital')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                    'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )
    readonly_fields = ['date_joined', 'last_login']
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(DonorProfile)
class DonorProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_blood_type', 'is_eligible', 'last_donation_date', 'city']
    list_filter = ['blood_group', 'rhesus_factor', 'is_eligible', 'state']
    search_fields = ['user__email', 'user__username', 'user__full_name', 'phone_number']
    readonly_fields = ['created_at']


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ['email', 'ip_address', 'successful', 'attempted_at']
    list_filter = ['successful']
    search_fields = ['email', 'ip_address']
