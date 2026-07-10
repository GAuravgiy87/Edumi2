import os
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse


def project_upload_path(instance, filename):
    """Store uploads under media/videos/<user_id>/<uuid>_<filename>."""
    ext = os.path.splitext(filename)[1]
    new_name = f"{uuid.uuid4().hex}{ext}"
    return f"videos/{instance.owner_id}/{new_name}"


class VideoProject(models.Model):
    """
    A VideoProject wraps a single working video plus its metadata.
    Every edit operation (trim, mute, overlay, merge, ...) produces a new
    'current_file' and is logged as an EditOperation, so users can see a
    history of what happened. This keeps editing simple: each action re-runs
    ffmpeg on the current state and replaces it, rather than modeling a
    full non-destructive timeline.
    """

    STATUS_CHOICES = [
        ("ready", "Ready"),
        ("processing", "Processing"),
        ("error", "Error"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=255, blank=True, default="")

    # The original file the user uploaded - never modified, kept for reference.
    original_file = models.FileField(upload_to=project_upload_path)

    # The current working file - this is what gets edited/replaced each operation.
    current_file = models.FileField(upload_to=project_upload_path, blank=True, null=True)

    duration_seconds = models.FloatField(blank=True, null=True)
    width = models.IntegerField(blank=True, null=True)
    height = models.IntegerField(blank=True, null=True)
    has_audio = models.BooleanField(default=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ready")
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    @property
    def display_title(self):
        import re
        cleaned_title = self.title.strip()
        if cleaned_title and cleaned_title != "Untitled Project":
            if re.match(r'^[a-f0-9]{32}$', cleaned_title):
                return "Video Project"
            return cleaned_title
        if self.original_file:
            orig_name = os.path.basename(self.original_file.name)
            name_without_ext = os.path.splitext(orig_name)[0]
            if re.match(r'^[a-f0-9]{32}$', name_without_ext):
                return "Video Project"
            return orig_name
        return "Untitled Project"

    def __str__(self):
        return f"{self.display_title} ({self.owner})"

    def get_absolute_url(self):
        return reverse("project_detail", kwargs={"pk": self.pk})

    @property
    def display_duration(self):
        if not self.duration_seconds:
            return ""
        secs = self.duration_seconds
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = int(secs % 60)
        ms = int(round((secs % 1) * 10))
        if h > 0:
            time_str = f"{h}:{m:02d}:{s:02d}"
        else:
            time_str = f"{m}:{s:02d}"
        if ms > 0:
            time_str += f".{ms}"
        return time_str

    @property
    def working_file(self):

        """The file that edit operations should act on."""
        return self.current_file if self.current_file else self.original_file


class EditOperation(models.Model):
    """A single logged edit action, for display in the project history panel."""

    OPERATION_CHOICES = [
        ("upload", "Uploaded"),
        ("trim", "Trimmed / Cut"),
        ("mute", "Muted Audio"),
        ("unmute", "Unmuted Audio"),
        ("volume", "Adjusted Volume"),
        ("merge", "Merged Clip"),
        ("text_overlay", "Added Text Overlay"),
        ("speed", "Changed Speed"),
        ("rotate", "Rotated"),
        ("resize", "Resized"),
        ("grayscale", "Applied Grayscale"),
        ("fade", "Applied Fade"),
        ("reset", "Reset to Original"),
    ]

    project = models.ForeignKey(VideoProject, on_delete=models.CASCADE, related_name="operations")
    operation_type = models.CharField(max_length=30, choices=OPERATION_CHOICES)
    description = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_operation_type_display()} on {self.project.title}"
