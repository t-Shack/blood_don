"""Root URL configuration for BDMIS."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('apps.core.urls')),
    path('', include('apps.accounts.urls')),
    path('hospitals/', include('apps.hospitals.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('requests/', include('apps.requests.urls')),
    path('donations/', include('apps.donations.urls')),
    path('notifications/', include('apps.notifications.urls')),

    path('api/', include('apps.core.api_urls')),
]

handler403 = core_views.error_403
handler404 = core_views.error_404
handler500 = core_views.error_500

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
