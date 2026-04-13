from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.http import HttpResponse

# Override admin logout to redirect to login page
admin.site.logout_template = None


def health_check(request):
    return HttpResponse("OK", content_type="text/plain", status=200)


urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
    path('admin/logout/', auth_views.LogoutView.as_view(next_page='/'), name='admin-logout'),
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('cameras/', include('cameras.urls')),
    path('mobile-cameras/', include('mobile_cameras.urls')),
    path('meetings/', include('meetings.urls')),
    path('attendance/', include('attendance.urls')),
    path("__reload__/", include("django_browser_reload.urls")),
]

# Error handlers
handler404 = 'accounts.views.error_404'
handler500 = 'accounts.views.error_500'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
