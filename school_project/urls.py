from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('cameras/', include('cameras.urls')),
    path('mobile-cameras/', include('mobile_cameras.urls')),
    path('meetings/', include('meetings.urls')),
    path("__reload__/", include("django_browser_reload.urls")),
]

# Error handlers
handler404 = 'accounts.views.error_404'
handler500 = 'accounts.views.error_500'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
