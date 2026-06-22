from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from meetings.livekit_http_proxy import livekit_http_proxy
from cameras.views_logic.camera_views import camera_feed

# Override admin logout to redirect to login page
admin.site.logout_template = None

# Debug camera feed
from django.http import HttpResponse
def test_camera_feed(request, camera_id):
    return HttpResponse(f"Camera {camera_id} feed route hit!", status=200)

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
    path('admin/logout/', auth_views.LogoutView.as_view(next_page='/'), name='admin-logout'),
    path('admin/', admin.site.urls),
    # LiveKit HTTP proxy — must be before other routes
    re_path(r'^livekit-proxy(?P<lk_path>/.*)$', livekit_http_proxy),
    path('', include('accounts.urls')),
    # Put the most specific route first: /cameras/<int:camera_id>/feed/
    path('cameras/<int:camera_id>/feed/', camera_feed, name='camera_feed_direct'),  # <-- Direct feed route first!
    path('cameras/', include('cameras.urls')),
    path('mobile-cameras/', include('mobile_cameras.urls')),
    path('meetings/', include('meetings.urls')),
    path('attendance/', include('attendance.urls')),
    path('videos/', include('videos.urls')),  # <-- Video URLs
    path('video-editing/', include('video_editing.urls')),  # <-- Video editing URLs
]

# Error handlers
handler404 = 'accounts.views.error_404'
handler500 = 'accounts.views.error_500'

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
