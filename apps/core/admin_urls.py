from django.urls import path

from . import admin_views

urlpatterns = [
    path('', admin_views.dashboard, name='admin_dashboard'),

    path('hospitals/', admin_views.hospital_list, name='admin_hospitals'),
    path('hospitals/add/', admin_views.hospital_add, name='admin_hospital_add'),
    path('hospitals/<int:pk>/edit/', admin_views.hospital_edit, name='admin_hospital_edit'),
    path('hospitals/<int:pk>/toggle/', admin_views.hospital_toggle, name='admin_hospital_toggle'),
    path('hospitals/<int:pk>/inventory/', admin_views.hospital_inventory_edit,
         name='admin_hospital_inventory'),

    path('users/', admin_views.user_list, name='admin_users'),
    path('users/add/', admin_views.user_add, name='admin_user_add'),
    path('users/<int:pk>/edit/', admin_views.user_edit, name='admin_user_edit'),
    path('users/<int:pk>/toggle/', admin_views.user_toggle, name='admin_user_toggle'),

    path('requests/', admin_views.request_overview, name='admin_requests'),

    path('criteria/', admin_views.criteria_list, name='admin_criteria'),
    path('criteria/add/', admin_views.criteria_add, name='admin_criteria_add'),
    path('criteria/<int:pk>/edit/', admin_views.criteria_edit, name='admin_criteria_edit'),
    path('criteria/<int:pk>/delete/', admin_views.criteria_delete, name='admin_criteria_delete'),

    path('notifications/', admin_views.notification_log, name='admin_notifications'),
]
