from django.urls import path

from . import views

app_name = 'donations'

urlpatterns = [
    path('', views.donation_list, name='list'),
    path('record/', views.donation_record, name='record'),
]
