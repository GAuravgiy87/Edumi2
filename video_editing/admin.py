from django.contrib import admin
from .models import VideoEditSession, VideoEditAction


class VideoEditActionInline(admin.TabularInline):
    model = VideoEditAction
    extra = 0


@admin.register(VideoEditSession)
class VideoEditSessionAdmin(admin.ModelAdmin):
    list_display = ['original_video', 'created_by', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['original_video__title', 'created_by__username']
    inlines = [VideoEditActionInline]


@admin.register(VideoEditAction)
class VideoEditActionAdmin(admin.ModelAdmin):
    list_display = ['session', 'action_type', 'order', 'created_at']
    list_filter = ['action_type', 'created_at']
    search_fields = ['session__original_video__title']
    readonly_fields = ['audio_file']