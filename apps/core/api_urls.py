from django.urls import path

from . import api_views

app_name = 'api'

urlpatterns = [
    path('inventory/', api_views.inventory_overview, name='inventory_overview'),
    path('inventory/<int:hospital_id>/', api_views.hospital_inventory, name='hospital_inventory'),
    path('hospitals/in-shortage/', api_views.hospitals_in_shortage, name='hospitals_in_shortage'),
    path('donor/eligibility/', api_views.donor_eligibility, name='donor_eligibility'),
    path('requests/<int:pk>/fulfill/', api_views.fulfil_request, name='fulfil_request'),
]
