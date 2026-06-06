"""
Video editing models for tracking edit sessions and actions.
"""
import os
from uuid import uuid4
from django.db import models
from django.conf import settings
from django.utils import timezone
from videos.models import Video


def edited_video_upload_path(instance, filename):
    """Generate unique upload path for edited videos."""
    ext = filename.split('.')[-1].lower()
    return f'edited_videos/{uuid4()}.{ext}'


def audio_upload_path(instance, filename):
    """Generate unique upload path for audio files."""
    ext = filename.split('.')[-1].lower()
    return f'edited_videos/audio/{uuid4()}.{ext}'


class VideoEditSession(models.Model):
    """Model to track a video editing session."""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    original_video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='edit_sessions')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='edit_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    edited_video = models.FileField(upload_to=edited_video_upload_path, blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Edit session for {self.original_video.title} by {self.created_by.username}"


class VideoEditAction(models.Model):
    """Model to track individual edit actions applied to a video."""
    
    ACTION_TYPE_CHOICES = [
        ('split', 'Split Video'),
        ('mute', 'Mute Audio'),
        ('unmute', 'Unmute Audio'),
        ('trim', 'Trim Video'),
        ('crop', 'Crop Video'),
        ('rotate', 'Rotate Video'),
        ('add_text', 'Add Text Overlay'),
        ('add_audio', 'Add/Overlay Audio'),
        ('replace_audio', 'Replace Audio'),
    ]
    
    session = models.ForeignKey(VideoEditSession, on_delete=models.CASCADE, related_name='actions')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPE_CHOICES)
    parameters = models.JSONField(default=dict)  # Stores action-specific parameters
    audio_file = models.FileField(upload_to=audio_upload_path, blank=True, null=True)
    order = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ('session', 'order')
    
    def __str__(self):
        return f"{self.get_action_type_display()} on {self.session}"