# Complete Video Editor Implementation Guide
**A Copy-Paste Ready Guide for Building a Browser-Based Video Editor**

---

## 📋 Table of Contents
1. [Quick Start Summary](#quick-start-summary)
2. [System Requirements](#system-requirements)
3. [Project Structure](#project-structure)
4. [Database Models (Complete Code)](#database-models-complete-code)
5. [FFmpeg Utility Functions (Complete Code)](#ffmpeg-utility-functions-complete-code)
6. [Django Views Implementation](#django-views-implementation)
7. [Forms and Validation](#forms-and-validation)
8. [URL Configuration](#url-configuration)
9. [Frontend: HTML Templates](#frontend-html-templates)
10. [Frontend: CSS Styling](#frontend-css-styling)
11. [Frontend: JavaScript Timeline](#frontend-javascript-timeline)
12. [Settings Configuration](#settings-configuration)
13. [Deployment Checklist](#deployment-checklist)
14. [Integration into Existing Projects](#integration-into-existing-projects)

---

## Quick Start Summary

### What This System Does
- **Upload videos** via browser (MP4, MOV, AVI, MKV, WebM)
- **Edit videos** with 15+ operations (trim, merge, text overlays, speed, rotate, resize, effects)
- **Visual timeline** with multi-track display (text, video, audio)
- **Undo/Redo** with full edit history
- **Real-time preview** of text overlays and positioning
- **Audio mixing** (volume control, background music)
- **Export** processed videos

### Technology Stack
- **Backend**: Python 3.10+ with Django 6.0+
- **Video Processing**: FFmpeg + FFprobe
- **Database**: SQLite (or PostgreSQL/MySQL)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Storage**: Local filesystem (or S3-compatible)

### Architecture Pattern
```
User uploads video → Stored as original_file (never modified)
                  ↓
User applies edits → FFmpeg processes current_file → New current_file
                  ↓
Each edit logged → EditOperation record → Undo/Redo capability
```

---

## System Requirements

### Software Dependencies
```bash
# Python packages
Django==6.0.6
asgiref==3.11.1
sqlparse==0.5.5
tzdata==2026.2

# System binaries (must be installed)
FFmpeg 4.0+
FFprobe 4.0+
```

### Installation Commands

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg python3-pip python3-venv
```

**macOS:**
```bash
brew install ffmpeg python3
```

**Windows:**
1. Download FFmpeg from https://ffmpeg.org/download.html
2. Extract and add to PATH
3. Install Python 3.10+ from python.org

### Disk Space Requirements
- Minimum: 2GB for application + dependencies
- Recommended: 10GB+ for video file storage
- Production: Scale based on expected concurrent users × average video size

---

## Project Structure

```
video_editor_project/
├── manage.py
├── requirements.txt
├── db.sqlite3
├── config/                         # Django project settings
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── editor/                         # Main application
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                   # VideoProject, EditOperation
│   ├── views.py                    # All request handlers
│   ├── forms.py                    # Form validation
│   ├── urls.py                     # URL routing
│   ├── ffmpeg_utils.py             # Video processing functions
│   ├── migrations/
│   ├── templates/
│   │   └── editor/
│   │       ├── base.html
│   │       ├── login.html
│   │       ├── signup.html
│   │       ├── project_list.html
│   │       ├── project_upload.html
│   │       └── project_detail.html  # Main editor interface
│   └── static/
│       └── editor/
│           ├── css/
│           │   └── style.css        # Complete styling
│           └── js/
│               └── app.js           # Timeline & interactions
└── media/                          # User uploads (gitignored)
    ├── videos/
    │   └── <user_id>/
    │       └── <video_files>
    └── tmp/                        # Temporary processing files
```

---

## Database Models (Complete Code)

### File: `editor/models.py`

```python
import os
import uuid
from django.conf import settings
from django.db import models
from django.urls import reverse


def project_upload_path(instance, filename):
    """Store uploads under media/videos/<user_id>/<uuid>_<filename>."""
    ext = os.path.splitext(filename)[1]
    new_name = f"{uuid.uuid4().hex}{ext}"
    if hasattr(instance, "owner_id"):
        owner_id = instance.owner_id
    elif hasattr(instance, "project") and hasattr(instance.project, "owner_id"):
        owner_id = instance.project.owner_id
    else:
        owner_id = "unknown"
    return f"videos/{owner_id}/{new_name}"


class VideoProject(models.Model):
    """
    A VideoProject wraps a single working video plus its metadata.
    Each edit operation produces a new current_file and is logged.
    """
    STATUS_CHOICES = [
        ("ready", "Ready"),
        ("processing", "Processing"),
        ("error", "Error"),
    ]

    # Ownership
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="projects"
    )
    title = models.CharField(max_length=255, blank=True, default="")

    # Files
    original_file = models.FileField(upload_to=project_upload_path)
    current_file = models.FileField(upload_to=project_upload_path, blank=True, null=True)

    # Metadata (cached from FFprobe)
    duration_seconds = models.FloatField(blank=True, null=True)
    width = models.IntegerField(blank=True, null=True)
    height = models.IntegerField(blank=True, null=True)
    has_audio = models.BooleanField(default=True)
    
    # Timeline state
    trim_start = models.FloatField(default=0.0)
    trim_end = models.FloatField(blank=True, null=True)

    # Processing status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ready")
    error_message = models.TextField(blank=True, default="")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.display_title} ({self.owner})"

    def get_absolute_url(self):
        return reverse("project_detail", kwargs={"pk": self.pk})

    @property
    def display_title(self):
        """Clean display of title, falling back to filename."""
        import re
        cleaned = self.title.strip()
        if cleaned and not re.match(r'^[a-f0-9]{32}$', cleaned):
            return cleaned
        if self.original_file:
            name = os.path.basename(self.original_file.name)
            name_no_ext = os.path.splitext(name)[0]
            if not re.match(r'^[a-f0-9]{32}$', name_no_ext):
                return os.path.basename(self.original_file.name)
        return "Untitled Project"

    @property
    def display_duration(self):
        """Format duration as H:MM:SS or M:SS.ms"""
        if not self.duration_seconds:
            return ""
        secs = self.duration_seconds
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = int(secs % 60)
        ms = int(round((secs % 1) * 10))
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}.{ms}" if ms > 0 else f"{m}:{s:02d}"

    @property
    def working_file(self):
        """The file that edit operations should act on."""
        return self.current_file if self.current_file else self.original_file


class EditOperation(models.Model):
    """A single logged edit action for history and undo/redo."""
    OPERATION_CHOICES = [
        ("upload", "Uploaded"),
        ("trim", "Trimmed / Cut"),
        ("mute", "Muted Audio"),
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

    project = models.ForeignKey(
        VideoProject, 
        on_delete=models.CASCADE, 
        related_name="operations"
    )
    operation_type = models.CharField(max_length=30, choices=OPERATION_CHOICES)
    description = models.CharField(max_length=500, blank=True, default="")
    
    # State snapshot
    video_file = models.FileField(upload_to=project_upload_path, blank=True, null=True)
    resource_file = models.FileField(upload_to=project_upload_path, blank=True, null=True)
    parameters = models.JSONField(blank=True, null=True)
    
    trim_start = models.FloatField(default=0.0)
    trim_end = models.FloatField(blank=True, null=True)
    
    # History management
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_operation_type_display()} on {self.project.title}"


# Signal to clean up files when operation is deleted
from django.dispatch import receiver

@receiver(models.signals.post_delete, sender=EditOperation)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """Delete video_file and resource_file from filesystem when operation is deleted."""
    for f in [instance.video_file, instance.resource_file]:
        if f and f.name:
            try:
                if os.path.isfile(f.path):
                    os.remove(f.path)
            except OSError:
                pass
```

### Database Schema Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     User (Django Auth)                       │
│  id | username | email | password | ...                     │
└──────────────────────┬──────────────────────────────────────┘
                       │ 1:N (owner)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                     VideoProject                             │
│  ─────────────────────────────────────────────────────────  │
│  id                  : Integer (PK)                          │
│  owner_id            : ForeignKey(User)                      │
│  title               : String                                │
│  original_file       : FileField (never modified)            │
│  current_file        : FileField (result of latest edit)     │
│  duration_seconds    : Float                                 │
│  width, height       : Integer                               │
│  has_audio           : Boolean                               │
│  trim_start, trim_end: Float                                 │
│  status              : Enum(ready, processing, error)        │
│  error_message       : Text                                  │
│  created_at          : DateTime                              │
│  updated_at          : DateTime                              │
└──────────────────────┬──────────────────────────────────────┘
                       │ 1:N
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    EditOperation                             │
│  ─────────────────────────────────────────────────────────  │
│  id                  : Integer (PK)                          │
│  project_id          : ForeignKey(VideoProject)              │
│  operation_type      : Enum(upload, trim, merge, text, ...) │
│  description         : String (human-readable)               │
│  video_file          : FileField (snapshot of result)        │
│  resource_file       : FileField (merge clip, audio)         │
│  parameters          : JSON (operation params)               │
│  trim_start, trim_end: Float                                 │
│  active              : Boolean (for undo/redo)               │
│  created_at          : DateTime                              │
└─────────────────────────────────────────────────────────────┘
```

---

## FFmpeg Utility Functions (Complete Code)

### File: `editor/ffmpeg_utils.py`

```python
"""
FFmpeg wrapper for video editing operations.
Each function takes input path(s) and returns a temp output file path.
"""
import json
import os
import subprocess
import tempfile
import uuid
from django.conf import settings


class FFmpegError(Exception):
    """Raised when ffmpeg/ffprobe command fails."""
    pass


def _run(cmd):
    """Run command and raise FFmpegError on failure."""
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="ignore")
        raise FFmpegError(stderr[-3000:])
    return result


def _tmp_path(suffix=".mp4"):
    """Generate temp file path in media/tmp/."""
    tmp_dir = os.path.join(settings.MEDIA_ROOT, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    return os.path.join(tmp_dir, f"{uuid.uuid4().hex}{suffix}")


def probe(path):
    """Return parsed ffprobe JSON for a media file."""
    cmd = [
        settings.FFPROBE_BINARY,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    result = _run(cmd)
    return json.loads(result.stdout.decode("utf-8"))


def get_metadata(path):
    """Extract duration, width, height, has_audio from media file."""
    data = probe(path)
    duration = None
    width = height = None
    has_audio = False

    fmt = data.get("format", {})
    if fmt.get("duration"):
        try:
            duration = float(fmt["duration"])
        except (TypeError, ValueError):
            pass

    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and width is None:
            width = stream.get("width")
            height = stream.get("height")
            if duration is None and stream.get("duration"):
                try:
                    duration = float(stream["duration"])
                except (TypeError, ValueError):
                    pass
        elif stream.get("codec_type") == "audio":
            has_audio = True

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "has_audio": has_audio,
    }


def trim(input_path, start_seconds, end_seconds):
    """Cut video to [start, end] range using fast stream copy."""
    out_path = _tmp_path()
    duration = max(0.0, float(end_seconds) - float(start_seconds))
    cmd = [
        settings.FFMPEG_BINARY, "-y",
        "-ss", str(start_seconds),
        "-i", input_path,
        "-t", str(duration),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        out_path,
    ]
    _run(cmd)
    return out_path


def mute(input_path):
    """Remove audio track entirely."""
    out_path = _tmp_path()
    cmd = [
        settings.FFMPEG_BINARY, "-y",
        "-i", input_path,
        "-c:v", "copy",
        "-an",
        out_path,
    ]
    _run(cmd)
    return out_path


def set_volume(input_path, volume_multiplier):
    """Adjust audio volume (0.0=silent, 1.0=original, 2.0=double)."""
    meta = get_metadata(input_path)
    out_path = _tmp_path()
    if not meta["has_audio"]:
        cmd = [settings.FFMPEG_BINARY, "-y", "-i", input_path, "-c", "copy", out_path]
    else:
        cmd = [
            settings.FFMPEG_BINARY, "-y",
            "-i", input_path,
            "-c:v", "copy",
            "-filter:a", f"volume={volume_multiplier}",
            out_path,
        ]
    _run(cmd)
    return out_path


def merge(input_paths):
    """
    Concatenate multiple videos into single output.
    Handles different resolutions and missing audio tracks.
    """
    out_path = _tmp_path()
    metas = [get_metadata(p) for p in input_paths]

    # Target dimensions from first clip
    target_width = metas[0]["width"] or 1280
    target_height = metas[0]["height"] or 720
    target_width += target_width % 2  # Ensure even for h264
    target_height += target_height % 2

    cmd = [settings.FFMPEG_BINARY, "-y"]
    for p in input_paths:
        cmd += ["-i", p]

    # Add silent audio for clips without audio
    n = len(input_paths)
    silent_input_indices = {}
    next_input_index = n
    for i, meta in enumerate(metas):
        if not meta["has_audio"]:
            duration = meta["duration"] or 1.0
            cmd += [
                "-f", "lavfi", "-t", str(duration),
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            ]
            silent_input_indices[i] = next_input_index
            next_input_index += 1

    # Build filter_complex to scale and concat
    filter_chunks = []
    concat_refs = []
    for i in range(n):
        video_label = f"v{i}"
        filter_chunks.append(
            f"[{i}:v:0]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,setsar=1[{video_label}]"
        )
        audio_ref = f"[{silent_input_indices[i]}:a:0]" if i in silent_input_indices else f"[{i}:a:0]"
        concat_refs.append(f"[{video_label}]{audio_ref}")

    filter_complex = (
        ";".join(filter_chunks) + ";" + 
        "".join(concat_refs) + 
        f"concat=n={n}:v=1:a=1[outv][outa]"
    )

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", "0",
        "-c:a", "aac",
        out_path,
    ]
    _run(cmd)
    return out_path


def add_text_overlay(input_path, text, position="bottom", font_size=80,
                      color="white", start_seconds=None, end_seconds=None):
    """
    Burn text overlay onto video using drawtext filter.
    position: 'top'|'bottom'|'center' or 'custom:x_pct,y_pct'
    """
    out_path = _tmp_path()

    # Handle custom positioning
    if isinstance(position, str) and position.startswith("custom:"):
        try:
            parts = position[7:].split(",")
            x_pct = float(parts[0])
            y_pct = float(parts[1])
            pos = f"x=(w-text_w)*{x_pct/100:.3f}:y=(h-text_h)*{y_pct/100:.3f}"
        except Exception:
            pos = "x=(w-text_w)/2:y=h-th-40"
    else:
        position_map = {
            "top": "x=(w-text_w)/2:y=40",
            "bottom": "x=(w-text_w)/2:y=h-th-40",
            "center": "x=(w-text_w)/2:y=(h-text_h)/2",
        }
        pos = position_map.get(position, position_map["bottom"])

    # Escape text for ffmpeg filter
    safe_text = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019")

    # Time window for text display
    enable_clause = ""
    if start_seconds is not None and end_seconds is not None:
        enable_clause = f":enable='between(t,{start_seconds},{end_seconds})'"

    # Font path (adjust for your OS)
    font_path = "C\\:/Windows/Fonts/arial.ttf"  # Windows
    # font_path = "/System/Library/Fonts/Helvetica.ttc"  # macOS
    # font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Linux

    drawtext = (
        f"drawtext=fontfile='{font_path}':text='{safe_text}':"
        f"fontcolor={color}:fontsize={font_size}:"
        f"box=1:boxcolor=black@0.5:boxborderw=8:{pos}{enable_clause}"
    )

    cmd = [
        settings.FFMPEG_BINARY, "-y",
        "-i", input_path,
        "-vf", drawtext,
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", "0",
        "-c:a", "copy",
        out_path,
    ]
    _run(cmd)
    return out_path


def change_speed(input_path, speed_factor):
    """
    Change playback speed (>1 = faster, <1 = slower).
    Handles audio with chained atempo filters for extreme speeds.
    """
    out_path = _tmp_path()
    meta = get_metadata(input_path)

    video_filter = f"setpts={1/speed_factor}*PTS"

    # Build audio filter (atempo only supports 0.5-2.0 per filter)
    atempo_filters = []
    remaining = speed_factor
    while remaining > 2.0:
        atempo_filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        atempo_filters.append("atempo=0.5")
        remaining /= 0.5
    atempo_filters.append(f"atempo={remaining}")
    audio_filter = ",".join(atempo_filters)

    if meta["has_audio"]:
        cmd = [
            settings.FFMPEG_BINARY, "-y",
            "-i", input_path,
            "-filter_complex", f"[0:v]{video_filter}[v];[0:a]{audio_filter}[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "0",
            "-c:a", "aac",
            out_path,
        ]
    else:
        cmd = [
            settings.FFMPEG_BINARY, "-y",
            "-i", input_path,
            "-vf", video_filter,
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "0",
            "-an",
            out_path,
        ]
    _run(cmd)
    return out_path


def rotate(input_path, degrees):
    """Rotate video by 90, 180, or 270 degrees clockwise."""
    out_path = _tmp_path()
    degrees = int(degrees) % 360
    transpose_map = {
        90: "transpose=1", 
        180: "transpose=1,transpose=1", 
        270: "transpose=2"
    }
    vf = transpose_map.get(degrees)
    if vf is None:
        raise FFmpegError("Rotation must be 90, 180, or 270 degrees.")
    cmd = [
        settings.FFMPEG_BINARY, "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", "0",
        "-c:a", "copy",
        out_path,
    ]
    _run(cmd)
    return out_path


def resize(input_path, width, height):
    """Resize video to exact dimensions (must be even for h264)."""
    out_path = _tmp_path()
    width = int(width) + (int(width) % 2)
    height = int(height) + (int(height) % 2)
    cmd = [
        settings.FFMPEG_BINARY, "-y",
        "-i", input_path,
        "-vf", f"scale={width}:{height}",
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", "0",
        "-c:a", "copy",
        out_path,
    ]
    _run(cmd)
    return out_path


def apply_grayscale(input_path):
    """Convert video to grayscale."""
    out_path = _tmp_path()
    cmd = [
        settings.FFMPEG_BINARY, "-y",
        "-i", input_path,
        "-vf", "hue=s=0",
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", "0",
        "-c:a", "copy",
        out_path,
    ]
    _run(cmd)
    return out_path


def apply_fade(input_path, fade_in_seconds=1.0, fade_out_seconds=1.0):
    """Apply fade-in at start and fade-out at end."""
    meta = get_metadata(input_path)
    duration = meta["duration"] or 0
    fade_out_start = max(0.0, duration - fade_out_seconds)

    out_path = _tmp_path()
    vf = f"fade=t=in:st=0:d={fade_in_seconds},fade=t=out:st={fade_out_start}:d={fade_out_seconds}"
    cmd = [
        settings.FFMPEG_BINARY, "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", "0",
        "-c:a", "copy",
        out_path,
    ]
    _run(cmd)
    return out_path


def add_background_audio(video_path, audio_path, bg_volume=0.5, video_volume=1.0,
                         start_seconds=0.0, end_seconds=None):
    """Mix external audio file as background music."""
    meta = get_metadata(video_path)
    duration = meta["duration"] or 0.0
    has_audio = meta["has_audio"]
    out_path = _tmp_path()
    
    start_seconds = float(start_seconds or 0.0)
    start_ms = int(start_seconds * 1000)
    bg_duration = (float(end_seconds) - start_seconds) if end_seconds else (duration - start_seconds)
    
    # Trim and delay background audio
    atrim_filter = f"atrim=0:{bg_duration},asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"
    
    if start_ms > 0:
        delay_filter = f"adelay={start_ms}:all=1"
        bg_filter = f"[1:a]{atrim_filter},{delay_filter},volume={bg_volume}[a_bg]"
    else:
        bg_filter = f"[1:a]{atrim_filter},volume={bg_volume}[a_bg]"
        
    if has_audio:
        filter_complex = (
            f"[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume={video_volume}[a_vid];"
            f"{bg_filter};"
            f"[a_vid][a_bg]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[a_out]"
        )
        cmd = [
            settings.FFMPEG_BINARY, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[a_out]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            out_path
        ]
    else:
        filter_complex = f"{bg_filter};[a_bg]anull[a_out]"
        cmd = [
            settings.FFMPEG_BINARY, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[a_out]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            out_path
        ]
    _run(cmd)
    return out_path


def convert_to_mkv(input_path):
    """Convert to MKV container without re-encoding."""
    out_path = _tmp_path(suffix=".mkv")
    cmd = [
        settings.FFMPEG_BINARY, "-y",
        "-i", input_path,
        "-c", "copy",
        out_path,
    ]
    _run(cmd)
    return out_path
```

### FFmpeg Command Reference

| Operation | FFmpeg Command Pattern |
|-----------|------------------------|
| **Trim** | `ffmpeg -ss START -i input.mp4 -t DURATION -c copy output.mp4` |
| **Mute** | `ffmpeg -i input.mp4 -c:v copy -an output.mp4` |
| **Volume** | `ffmpeg -i input.mp4 -c:v copy -filter:a "volume=2.0" output.mp4` |
| **Text** | `ffmpeg -i input.mp4 -vf "drawtext=text='Hello':fontsize=80" output.mp4` |
| **Speed** | `ffmpeg -i input.mp4 -filter_complex "[0:v]setpts=0.5*PTS[v];[0:a]atempo=2.0[a]" output.mp4` |
| **Rotate** | `ffmpeg -i input.mp4 -vf "transpose=1" output.mp4` |
| **Grayscale** | `ffmpeg -i input.mp4 -vf "hue=s=0" output.mp4` |
| **Fade** | `ffmpeg -i input.mp4 -vf "fade=t=in:st=0:d=1,fade=t=out:st=28:d=2" output.mp4` |

---

## Django Views Implementation

### File: `editor/views.py` (Core Functions)

```python
import os
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files import File
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from . import ffmpeg_utils
from .forms import (
    SignUpForm, VideoUploadForm, TrimForm, VolumeForm, 
    MergeForm, TextOverlayForm, SpeedForm, RotateForm, 
    ResizeForm, FadeForm
)
from .models import VideoProject, EditOperation


# ========== Authentication ==========

def signup_view(request):
    """User registration."""
    if request.user.is_authenticated:
        return redirect("project_list")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome! Your account was created.")
            return redirect("project_list")
    else:
        form = SignUpForm()
    return render(request, "editor/signup.html", {"form": form})


# ========== Project Management ==========

@login_required
def project_list(request):
    """List all projects for current user."""
    projects = VideoProject.objects.filter(owner=request.user)
    return render(request, "editor/project_list.html", {"projects": projects})


@login_required
def project_upload(request):
    """Handle video upload and metadata extraction."""
    if request.method == "POST":
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.status = "processing"
            
            # Set title from filename if empty
            if not project.title or not project.title.strip():
                orig_filename = request.FILES["original_file"].name
                project.title = os.path.splitext(orig_filename)[0]
            
            project.save()

            try:
                # Extract metadata with FFprobe
                meta = ffmpeg_utils.get_metadata(project.original_file.path)
                project.duration_seconds = meta["duration"]
                project.width = meta["width"]
                project.height = meta["height"]
                project.has_audio = meta["has_audio"]
                project.status = "ready"
                project.save()

                # Log upload operation
                EditOperation.objects.create(
                    project=project,
                    operation_type="upload",
                    description=f"Uploaded {project.original_file.name.split('/')[-1]}",
                )
                messages.success(request, "Video uploaded successfully.")
                return redirect("project_detail", pk=project.pk)
            except ffmpeg_utils.FFmpegError as e:
                project.status = "error"
                project.error_message = str(e)
                project.save()
                messages.error(request, "Could not read video metadata.")
                return redirect("project_detail", pk=project.pk)
    else:
        form = VideoUploadForm()
    return render(request, "editor/project_upload.html", {"form": form})


@login_required
def project_detail(request, pk):
    """Main editor interface."""
    project = get_object_or_404(VideoProject, pk=pk, owner=request.user)
    
    context = {
        "project": project,
        "trim_form": TrimForm(),
        "volume_form": VolumeForm(),
        "merge_form": MergeForm(),
        "text_form": TextOverlayForm(),
        "speed_form": SpeedForm(),
        "rotate_form": RotateForm(),
        "resize_form": ResizeForm(),
        "fade_form": FadeForm(),
        "operations": project.operations.filter(active=True)[:20],
        "has_redo": project.operations.filter(active=False).exists(),
    }
    return render(request, "editor/project_detail.html", context)


@login_required
def project_status(request, pk):
    """AJAX endpoint for polling processing status."""
    project = get_object_or_404(VideoProject, pk=pk, owner=request.user)
    return JsonResponse({"status": project.status})


@login_required
@require_POST
def project_delete(request, pk):
    """Delete project and all associated files."""
    project = get_object_or_404(VideoProject, pk=pk, owner=request.user)
    project.delete()
    messages.success(request, "Project deleted.")
    return redirect("project_list")


# ========== Helper: Apply Operation Result ==========

def _apply_new_working_file(project, tmp_output_path, operation_type, 
                            description, parameters=None):
    """
    Replace project's current_file with new processed file.
    Update metadata and log operation.
    """
    try:
        # Clear redo stack
        project.operations.filter(active=False).delete()

        # Save new file
        filename = os.path.basename(tmp_output_path)
        with open(tmp_output_path, "rb") as f:
            # Delete old current_file
            if project.current_file and project.current_file.name:
                try:
                    old_path = project.current_file.path
                    project.current_file.delete(save=False)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                except Exception:
                    pass

            project.current_file.save(filename, File(f), save=False)

        # Update metadata
        meta = ffmpeg_utils.get_metadata(project.current_file.path)
        project.duration_seconds = meta["duration"]
        project.width = meta["width"]
        project.height = meta["height"]
        project.has_audio = meta["has_audio"]
        project.status = "ready"
        project.error_message = ""
        project.save()

        # Log operation
        op = EditOperation.objects.create(
            project=project,
            operation_type=operation_type,
            description=description,
            parameters=parameters,
        )
        
        # Save snapshot of result
        with open(tmp_output_path, "rb") as f:
            op.video_file.save(filename, File(f), save=False)
        op.save()
        
    finally:
        # Clean up temp file
        if os.path.exists(tmp_output_path):
            try:
                os.remove(tmp_output_path)
            except OSError:
                pass


# ========== Edit Operations ==========

@login_required
@require_POST
def op_trim(request, pk):
    """Trim video to time range."""
    project = get_object_or_404(VideoProject, pk=pk, owner=request.user)
    form = TrimForm(request.POST)
    
    if not form.is_valid():
        for field, errors in form.errors.items():
            for err in errors:
                messages.error(request, f"{field}: {err}")
        return redirect("project_detail", pk=pk)

    project.status = "processing"
    project.save()

    try:
        tmp_output = ffmpeg_utils.trim(
            project.working_file.path,
            form.cleaned_data["start_seconds"],
            form.cleaned_data["end_seconds"]
        )
        _apply_new_working_file(
            project, tmp_output, "trim",
            f"Trimmed to {form.cleaned_data['start_seconds']}s - {form.cleaned_data['end_seconds']}s",
            parameters=form.cleaned_data
        )
        messages.success(request, "Video trimmed.")
    except ffmpeg_utils.FFmpegError as e:
        project.status = "error"
        project.error_message = str(e)
        project.save()
        messages.error(request, "Trimming failed.")

    return redirect("project_detail", pk=pk)


@login_required
@require_POST
def op_text_overlay(request, pk):
    """Add text overlay to video."""
    project = get_object_or_404(VideoProject, pk=pk, owner=request.user)
    form = TextOverlayForm(request.POST)
    
    if not form.is_valid():
        messages.error(request, "Invalid form data.")
        return redirect("project_detail", pk=pk)

    project.status = "processing"
    project.save()

    try:
        d = form.cleaned_data
        tmp_output = ffmpeg_utils.add_text_overlay(
            project.working_file.path,
            d["text"],
            position=d["position"],
            font_size=d["font_size"],
            color=d["color"],
            start_seconds=d.get("start_seconds"),
            end_seconds=d.get("end_seconds")
        )
        
        start = d.get("start_seconds") or 0.0
        end = d.get("end_seconds") or project.duration_seconds
        
        _apply_new_working_file(
            project, tmp_output, "text_overlay",
            f"Added text overlay: \"{d['text']}\" [start={start:.2f},end={end:.2f}]",
            parameters=d
        )
        messages.success(request, "Text overlay added.")
    except ffmpeg_utils.FFmpegError as e:
        project.status = "error"
        project.error_message = str(e)
        project.save()
        messages.error(request, "Text overlay failed.")

    return redirect("project_detail", pk=pk)


@login_required
@require_POST
def op_reset(request, pk):
    """Reset project to original uploaded file."""
    project = get_object_or_404(VideoProject, pk=pk, owner=request.user)
    
    # Deactivate all operations except upload
    for op in project.operations.exclude(operation_type="upload"):
        op.active = False
        op.save()
    
    # Reset current_file to None (falls back to original_file)
    if project.current_file and project.current_file.name:
        project.current_file.delete()
    project.current_file = None
    
    # Restore original metadata
    meta = ffmpeg_utils.get_metadata(project.original_file.path)
    project.duration_seconds = meta["duration"]
    project.width = meta["width"]
    project.height = meta["height"]
    project.has_audio = meta["has_audio"]
    project.status = "ready"
    project.save()
    
    messages.success(request, "Project reset to original.")
    return redirect("project_detail", pk=pk)
```

### View Functions Summary

| View Function | HTTP Method | Purpose |
|--------------|-------------|---------|
| `signup_view()` | GET/POST | User registration |
| `project_list()` | GET | Display user's projects |
| `project_upload()` | GET/POST | Upload and process new video |
| `project_detail()` | GET | Main editor interface |
| `project_status()` | GET (AJAX) | Poll processing status |
| `project_delete()` | POST | Delete project |
| `op_trim()` | POST | Trim video to time range |
| `op_mute()` | POST | Remove audio track |
| `op_volume()` | POST | Adjust audio volume |
| `op_merge()` | POST | Concatenate video clips |
| `op_text_overlay()` | POST | Add text overlay |
| `op_speed()` | POST | Change playback speed |
| `op_rotate()` | POST | Rotate video |
| `op_resize()` | POST | Resize dimensions |
| `op_grayscale()` | POST | Apply grayscale filter |
| `op_fade()` | POST | Add fade in/out |
| `op_reset()` | POST | Revert to original |
| `op_revert()` | POST | Undo to specific operation |
| `op_redo()` | POST | Redo last undone operation |

---

## Forms and Validation

### File: `editor/forms.py`

```python
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import VideoProject

ALLOWED_VIDEO_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"]


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]


class VideoUploadForm(forms.ModelForm):
    class Meta:
        model = VideoProject
        fields = ["title", "original_file"]

    def clean_original_file(self):
        f = self.cleaned_data["original_file"]
        ext = ("." + f.name.rsplit(".", 1)[-1]).lower() if "." in f.name else ""
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise forms.ValidationError(
                f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}"
            )
        if f.size > 500 * 1024 * 1024:  # 500MB
            raise forms.ValidationError("File too large (max 500MB)")
        return f


class TrimForm(forms.Form):
    start_seconds = forms.FloatField(min_value=0, label="Start (seconds)")
    end_seconds = forms.FloatField(min_value=0, label="End (seconds)")

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_seconds")
        end = cleaned.get("end_seconds")
        if start is not None and end is not None and end <= start:
            raise forms.ValidationError("End time must be after start time.")
        return cleaned


class VolumeForm(forms.Form):
    volume = forms.FloatField(
        min_value=0, max_value=5, initial=1.0,
        label="Volume multiplier (0=silent, 1=original, 2=double)"
    )


class MergeForm(forms.Form):
    clip_file = forms.FileField(label="Video clip to append")
    position = forms.ChoiceField(
        choices=[("end", "Add to end"), ("start", "Add to start")],
        initial="end"
    )


class TextOverlayForm(forms.Form):
    text = forms.CharField(max_length=200, widget=forms.TextInput(attrs={
        "class": "text-input", "placeholder": "Your caption here"
    }))
    position = forms.CharField(max_length=100, initial="bottom", 
                               widget=forms.Select(choices=[
        ("bottom", "Bottom"), ("top", "Top"), ("center", "Center"),
    ]))
    font_size = forms.IntegerField(min_value=10, max_value=400, initial=80)
    color = forms.ChoiceField(choices=[
        ("white", "White"), ("black", "Black"), ("yellow", "Yellow"),
        ("red", "Red"), ("cyan", "Cyan"),
    ], initial="white")
    start_seconds = forms.FloatField(required=False, min_value=0)
    end_seconds = forms.FloatField(required=False, min_value=0)


class SpeedForm(forms.Form):
    speed_factor = forms.FloatField(
        min_value=0.25, max_value=4.0, initial=1.0,
        label="Speed factor (0.25x - 4x)"
    )


class RotateForm(forms.Form):
    degrees = forms.ChoiceField(choices=[
        ("90", "90°"), ("180", "180°"), ("270", "270°")
    ])


class ResizeForm(forms.Form):
    width = forms.IntegerField(min_value=16, max_value=7680)
    height = forms.IntegerField(min_value=16, max_value=4320)


class FadeForm(forms.Form):
    fade_in_seconds = forms.FloatField(min_value=0, max_value=30, initial=1.0)
    fade_out_seconds = forms.FloatField(min_value=0, max_value=30, initial=1.0)
```

---

## URL Configuration

### File: `editor/urls.py`

```python
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path("signup/", views.signup_view, name="signup"),
    path("login/", auth_views.LoginView.as_view(
        template_name="editor/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Projects
    path("", views.project_list, name="project_list"),
    path("upload/", views.project_upload, name="project_upload"),
    path("project/<int:pk>/", views.project_detail, name="project_detail"),
    path("project/<int:pk>/delete/", views.project_delete, name="project_delete"),
    path("project/<int:pk>/status/", views.project_status, name="project_status"),

    # Edit operations
    path("project/<int:pk>/trim/", views.op_trim, name="op_trim"),
    path("project/<int:pk>/mute/", views.op_mute, name="op_mute"),
    path("project/<int:pk>/volume/", views.op_volume, name="op_volume"),
    path("project/<int:pk>/merge/", views.op_merge, name="op_merge"),
    path("project/<int:pk>/text/", views.op_text_overlay, name="op_text_overlay"),
    path("project/<int:pk>/speed/", views.op_speed, name="op_speed"),
    path("project/<int:pk>/rotate/", views.op_rotate, name="op_rotate"),
    path("project/<int:pk>/resize/", views.op_resize, name="op_resize"),
    path("project/<int:pk>/grayscale/", views.op_grayscale, name="op_grayscale"),
    path("project/<int:pk>/fade/", views.op_fade, name="op_fade"),
    path("project/<int:pk>/reset/", views.op_reset, name="op_reset"),
    path("project/<int:pk>/revert/<int:op_pk>/", views.op_revert, name="op_revert"),
    path("project/<int:pk>/redo/", views.op_redo, name="op_redo"),
]
```

### File: `config/urls.py`

```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("editor.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## Frontend: HTML Templates

### File: `editor/templates/editor/base.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Video Editor{% endblock %}</title>
    {% load static %}
    <link rel="stylesheet" href="{% static 'editor/css/style.css' %}">
</head>
<body>
    <!-- Top Navigation -->
    <nav class="topbar">
        <div class="brand">
            <span class="brand-mark">▶</span> Reel
        </div>
        {% if user.is_authenticated %}
        <div class="topnav">
            <a href="{% url 'project_list' %}" class="nav-link">Projects</a>
            <a href="{% url 'project_upload' %}" class="nav-link nav-link--accent">+ Upload</a>
            <span class="user-chip">{{ user.username }}</span>
            <form method="post" action="{% url 'logout' %}" style="display:inline; margin:0;">
                {% csrf_token %}
                <button type="submit" class="link-btn">Logout</button>
            </form>
        </div>
        {% else %}
        <div class="topnav">
            <a href="{% url 'login' %}" class="nav-link">Login</a>
            <a href="{% url 'signup' %}" class="nav-link nav-link--accent">Sign Up</a>
        </div>
        {% endif %}
    </nav>

    <!-- Messages -->
    {% if messages %}
    <div class="messages">
        {% for message in messages %}
        <div class="message message--{{ message.tags }}">{{ message }}</div>
        {% endfor %}
    </div>
    {% endif %}

    <!-- Main Content -->
    <main class="main">
        {% block content %}{% endblock %}
    </main>

    <!-- Footer -->
    <footer class="footer">
        <p>&copy; 2024 Video Editor. Built with Django + FFmpeg.</p>
    </footer>

    {% block extra_js %}{% endblock %}
    <script src="{% static 'editor/js/app.js' %}"></script>
</body>
</html>
```

### File: `editor/templates/editor/project_list.html`

```html
{% extends "editor/base.html" %}
{% block title %}Your Projects — Video Editor{% endblock %}
{% block content %}
<div class="page-head">
    <div>
        <h1 class="page-title">Your Projects</h1>
        <p class="page-sub">Every upload becomes a project you can edit and export.</p>
    </div>
    <a href="{% url 'project_upload' %}" class="btn btn--primary">+ Upload Video</a>
</div>

{% if projects %}
<div class="project-grid">
    {% for project in projects %}
    <a href="{% url 'project_detail' project.pk %}" class="project-card">
        <div class="project-card__thumb">
            <video muted preload="metadata" src="{{ project.working_file.url }}#t=0.5"></video>
            <span class="status-pill status-pill--{{ project.status }}">
                {{ project.get_status_display }}
            </span>
        </div>
        <div class="project-card__body">
            <h3>{{ project.display_title }}</h3>
            <p class="muted-text">
                {% if project.duration_seconds %}{{ project.display_duration }} ·{% endif %}
                {% if project.width %}{{ project.width }}×{{ project.height }}{% endif %}
            </p>
            <p class="muted-text muted-text--small">
                Updated {{ project.updated_at|timesince }} ago
            </p>
        </div>
    </a>
    {% endfor %}
</div>
{% else %}
<div class="empty-state">
    <p class="empty-state__icon">⧉</p>
    <h2>No projects yet</h2>
    <p>Upload a video to start editing.</p>
    <a href="{% url 'project_upload' %}" class="btn btn--primary">Upload your first video</a>
</div>
{% endif %}
{% endblock %}
```

### File: `editor/templates/editor/project_detail.html` (Editor Interface - Simplified)

```html
{% extends "editor/base.html" %}
{% block title %}{{ project.display_title }} — Editor{% endblock %}
{% block content %}
<div class="editor-layout">
    <!-- Main Editor Area -->
    <div class="editor-main">
        <div class="editor-head">
            <div>
                <h1 class="page-title">{{ project.display_title }}</h1>
                <p class="muted-text">
                    {{ project.display_duration }} · {{ project.width }}×{{ project.height }}
                </p>
            </div>
            <div class="editor-head__actions">
                <span class="status-pill status-pill--{{ project.status }}">
                    {{ project.get_status_display }}
                </span>
