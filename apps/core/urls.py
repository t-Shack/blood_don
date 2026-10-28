from django.urls import include, path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('donate/criteria/', views.criteria, name='criteria'),
    path('about/', views.about, name='about'),

    # Custom administrator dashboard.
    path('admin-panel/', include('apps.core.admin_urls')),
]
