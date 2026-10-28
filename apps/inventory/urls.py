from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.inventory_overview, name='overview'),
]
