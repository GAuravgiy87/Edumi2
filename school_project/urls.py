from django.contrib import admin
import os
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.http import JsonResponse
from meetings.livekit_http_proxy import livekit_http_proxy

# Override admin logout to redirect to login page
admin.site.logout_template = None


def health_check(request):
    """Load balancer health check — nginx polls this to verify worker is alive."""
    import os
    return JsonResponse({
        'status': 'ok',
        'worker_pid': os.getpid(),
    })

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
    path('health/', health_check, name='health_check'),   # load balancer probe
    path('admin/logout/', auth_views.LogoutView.as_view(next_page='/'), name='admin-logout'),
    path('admin/', admin.site.urls),
    # LiveKit HTTP proxy — must be before other routes
    re_path(r'^livekit-proxy(?P<lk_path>/.*)$', livekit_http_proxy),
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
    from django.contrib.staticfiles.views import serve as static_serve
    from django.views.static import serve as media_serve
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', static_serve),
        re_path(r'^media/(?P<path>.*)$', media_serve, {'document_root': settings.MEDIA_ROOT}),
    ]
