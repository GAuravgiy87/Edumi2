import os
import uuid

from django.conf import settings
from django.contrib import messages
from django.core.files import File
from django.http import FileResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from . import ffmpeg_utils
from .forms import (
    VideoUploadForm, TrimForm, VolumeForm, MergeForm,
    TextOverlayForm, SpeedForm, RotateForm, ResizeForm, FadeForm,
    BackgroundAudioForm,
)
from .models import VideoProject, EditOperation


# ---------------------------------------------------------------------------
# Project list / upload
# ---------------------------------------------------------------------------

def project_list(request):
    if request.method == "POST":
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.status = "processing"
            if not project.title or not project.title.strip():
                orig_filename = request.FILES["original_file"].name
                project.title = os.path.splitext(orig_filename)[0]
            project.save()
            try:
                meta = ffmpeg_utils.get_metadata(project.original_file.path)
                project.duration_seconds = meta["duration"]
                project.width = meta["width"]
                project.height = meta["height"]
                project.has_audio = meta["has_audio"]
                project.status = "ready"
                project.save()
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
                messages.error(request, "Could not read video metadata. Is the file a valid video?")
                return redirect("project_detail", pk=project.pk)
    else:
        form = VideoUploadForm()
    projects = VideoProject.objects.filter(owner=request.user)
    return render(request, "video_editing/project_list.html", {"projects": projects, "form": form})


def project_detail(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)

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
        "bg_audio_form": BackgroundAudioForm(),
        "operations": project.operations.all()[:20],
    }
    return render(request, "video_editing/project_detail.html", context)


# ---------------------------------------------------------------------------
# Helper: apply an ffmpeg operation result to the project + log it
# ---------------------------------------------------------------------------

def _apply_new_working_file(project, tmp_output_path, operation_type, description):
    """
    Take a temp file produced by ffmpeg_utils, attach it as the project's new
    current_file, refresh cached metadata, log the operation, and clean up.
    """
    try:
        filename = os.path.basename(tmp_output_path)
        with open(tmp_output_path, "rb") as f:
            # Delete old current_file from disk if it exists and isn't the original
            if project.current_file and project.current_file.name:
                old_path = project.current_file.path
                try:
                    project.current_file.delete(save=False)
                except Exception:
                    pass
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass

            project.current_file.save(filename, File(f), save=False)

        try:
            meta = ffmpeg_utils.get_metadata(project.current_file.path)
            project.duration_seconds = meta["duration"]
            project.width = meta["width"]
            project.height = meta["height"]
            project.has_audio = meta["has_audio"]
            project.status = "ready"
            project.error_message = ""
        finally:
            project.save()

        EditOperation.objects.create(
            project=project, operation_type=operation_type, description=description,
        )
    finally:
        if os.path.exists(tmp_output_path):
            try:
                os.remove(tmp_output_path)
            except OSError:
                pass


def _handle_operation(request, pk, form_class, run_ffmpeg_fn, operation_type,
                       describe_fn, extra_files=None):
    """
    Shared plumbing for all edit endpoints:
    1. Validate form
    2. Run the ffmpeg function against the current working file
    3. Save the result, log it, redirect back to project detail
    """
    project = get_object_or_404(VideoProject, pk=pk)

    if request.method != "POST":
        return redirect("project_detail", pk=pk)

    form = form_class(request.POST, request.FILES) if extra_files else form_class(request.POST)
    if not form.is_valid():
        for field, errors in form.errors.items():
            for err in errors:
                messages.error(request, f"{field}: {err}")
        return redirect("project_detail", pk=pk)

    project.status = "processing"
    project.save(update_fields=["status"])

    try:
        input_path = project.working_file.path
        tmp_output = run_ffmpeg_fn(input_path, form)
        description = describe_fn(form)
        _apply_new_working_file(project, tmp_output, operation_type, description)
        messages.success(request, f"{description} — done.")
    except ffmpeg_utils.FFmpegError as e:
        project.status = "error"
        project.error_message = str(e)
        project.save(update_fields=["status", "error_message"])
        messages.error(request, "Video processing failed. See error details below.")

    # Map operation_type to sidebar tab name
    tab_map = {
        "text_overlay": "text",
        "volume": "audio",
        "speed": "fx",
        "rotate": "fx",
        "resize": "fx",
        "grayscale": "fx",
        "fade": "fx",
        "trim": "audio",
    }
    tab = tab_map.get(operation_type, "audio")
    from django.urls import reverse
    return redirect(reverse("project_detail", args=[pk]) + f"?tab={tab}")


# ---------------------------------------------------------------------------
# Edit operation endpoints
# ---------------------------------------------------------------------------

@require_POST
def op_trim(request, pk):
    return _handle_operation(
        request, pk, TrimForm,
        run_ffmpeg_fn=lambda path, form: ffmpeg_utils.trim(
            path, form.cleaned_data["start_seconds"], form.cleaned_data["end_seconds"]
        ),
        operation_type="trim",
        describe_fn=lambda form: (
            f"Trimmed to {form.cleaned_data['start_seconds']}s - {form.cleaned_data['end_seconds']}s"
        ),
    )


@require_POST
def op_mute(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)
    project.status = "processing"
    project.save(update_fields=["status"])
    try:
        tmp_output = ffmpeg_utils.mute(project.working_file.path)
        _apply_new_working_file(project, tmp_output, "mute", "Muted audio track")
        messages.success(request, "Audio muted.")
    except ffmpeg_utils.FFmpegError as e:
        project.status = "error"
        project.error_message = str(e)
        project.save(update_fields=["status", "error_message"])
        messages.error(request, "Failed to mute audio.")
    from django.urls import reverse
    return redirect(reverse("project_detail", args=[pk]) + "?tab=audio")


@require_POST
def op_volume(request, pk):
    def describe(form):
        v = form.cleaned_data["volume"]
        if v == 0:
            return "Muted audio (volume set to 0)"
        return f"Set volume to {v}x"

    return _handle_operation(
        request, pk, VolumeForm,
        run_ffmpeg_fn=lambda path, form: ffmpeg_utils.set_volume(path, form.cleaned_data["volume"]),
        operation_type="volume",
        describe_fn=describe,
    )


@require_POST
def op_merge(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)

    form = MergeForm(request.POST, request.FILES)
    if not form.is_valid():
        for field, errors in form.errors.items():
            for err in errors:
                messages.error(request, f"{field}: {err}")
        return redirect("project_detail", pk=pk)

    project.status = "processing"
    project.save(update_fields=["status"])

    # Save the uploaded clip to a temp path first
    clip_file = form.cleaned_data["clip_file"]
    tmp_dir = os.path.join(settings.MEDIA_ROOT, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    clip_tmp_path = os.path.join(tmp_dir, f"upload_{clip_file.name}")
    with open(clip_tmp_path, "wb") as dest:
        for chunk in clip_file.chunks():
            dest.write(chunk)

    try:
        base_path = project.working_file.path
        position = form.cleaned_data["position"]
        if position == "start":
            paths = [clip_tmp_path, base_path]
        else:
            paths = [base_path, clip_tmp_path]

        tmp_output = ffmpeg_utils.merge(paths)
        _apply_new_working_file(
            project, tmp_output, "merge",
            f"Merged clip '{clip_file.name}' at {position}",
        )
        messages.success(request, "Clip merged successfully.")
    except ffmpeg_utils.FFmpegError as e:
        project.status = "error"
        project.error_message = str(e)
        project.save(update_fields=["status", "error_message"])
        messages.error(request, "Failed to merge clips. Ensure both videos are valid and have audio tracks.")
    finally:
        if os.path.exists(clip_tmp_path):
            try:
                os.remove(clip_tmp_path)
            except OSError:
                pass

    from django.urls import reverse
    return redirect(reverse("project_detail", args=[pk]) + "?tab=merge")


@require_POST
def op_text_overlay(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)
    duration = project.duration_seconds if project else 0.0

    def run(path, form):
        d = form.cleaned_data
        return ffmpeg_utils.add_text_overlay(
            path, d["text"], position=d["position"], font_size=d["font_size"],
            color=d["color"], start_seconds=d.get("start_seconds"), end_seconds=d.get("end_seconds"),
        )

    def describe(form):
        start = form.cleaned_data.get("start_seconds")
        if start is None:
            start = 0.0
        end = form.cleaned_data.get("end_seconds")
        if end is None:
            end = duration or 0.0
        return f"Added text overlay: \"{form.cleaned_data['text']}\" [start={start:.2f},end={end:.2f}]"

    return _handle_operation(
        request, pk, TextOverlayForm,
        run_ffmpeg_fn=run,
        operation_type="text_overlay",
        describe_fn=describe,
    )


@require_POST
def op_speed(request, pk):
    return _handle_operation(
        request, pk, SpeedForm,
        run_ffmpeg_fn=lambda path, form: ffmpeg_utils.change_speed(path, form.cleaned_data["speed_factor"]),
        operation_type="speed",
        describe_fn=lambda form: f"Changed speed to {form.cleaned_data['speed_factor']}x",
    )


@require_POST
def op_rotate(request, pk):
    return _handle_operation(
        request, pk, RotateForm,
        run_ffmpeg_fn=lambda path, form: ffmpeg_utils.rotate(path, int(form.cleaned_data["degrees"])),
        operation_type="rotate",
        describe_fn=lambda form: f"Rotated {form.cleaned_data['degrees']}°",
    )


@require_POST
def op_resize(request, pk):
    return _handle_operation(
        request, pk, ResizeForm,
        run_ffmpeg_fn=lambda path, form: ffmpeg_utils.resize(
            path, form.cleaned_data["width"], form.cleaned_data["height"]
        ),
        operation_type="resize",
        describe_fn=lambda form: f"Resized to {form.cleaned_data['width']}x{form.cleaned_data['height']}",
    )


@require_POST
def op_grayscale(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)
    project.status = "processing"
    project.save(update_fields=["status"])
    try:
        tmp_output = ffmpeg_utils.apply_grayscale(project.working_file.path)
        _apply_new_working_file(project, tmp_output, "grayscale", "Applied grayscale filter")
        messages.success(request, "Grayscale filter applied.")
    except ffmpeg_utils.FFmpegError as e:
        project.status = "error"
        project.error_message = str(e)
        project.save(update_fields=["status", "error_message"])
        messages.error(request, "Failed to apply grayscale filter.")
    return redirect("project_detail", pk=pk)


@require_POST
def op_fade(request, pk):
    return _handle_operation(
        request, pk, FadeForm,
        run_ffmpeg_fn=lambda path, form: ffmpeg_utils.apply_fade(
            path, form.cleaned_data["fade_in_seconds"], form.cleaned_data["fade_out_seconds"]
        ),
        operation_type="fade",
        describe_fn=lambda form: (
            f"Applied fade in ({form.cleaned_data['fade_in_seconds']}s) / "
            f"out ({form.cleaned_data['fade_out_seconds']}s)"
        ),
    )


@require_POST
def op_reset(request, pk):
    """Discard all edits and revert current_file back to the original upload."""
    project = get_object_or_404(VideoProject, pk=pk)

    if project.current_file and project.current_file.name:
        old_path = project.current_file.path
        try:
            project.current_file.delete(save=False)
        except Exception:
            pass
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    meta = ffmpeg_utils.get_metadata(project.original_file.path)
    project.duration_seconds = meta["duration"]
    project.width = meta["width"]
    project.height = meta["height"]
    project.has_audio = meta["has_audio"]
    project.status = "ready"
    project.error_message = ""
    project.save()

    EditOperation.objects.create(project=project, operation_type="reset", description="Reset to original upload")
    messages.success(request, "Project reset to the original uploaded video.")
    return redirect("project_detail", pk=pk)


@require_POST
def project_delete(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)
    title = project.display_title
    # Delete files from disk
    for f in [project.original_file, project.current_file]:
        if f and f.name and os.path.exists(f.path):
            try:
                os.remove(f.path)
            except OSError:
                pass
    project.delete()
    messages.success(request, f"Project '{title}' deleted.")
    return redirect("project_list")


def project_download(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)
    file_field = project.working_file
    response = FileResponse(open(file_field.path, "rb"), as_attachment=True,
                             filename=f"{project.display_title}{os.path.splitext(file_field.name)[1]}")
    return response


def project_download_mkv(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)
    
    file_field = project.working_file
    if os.path.splitext(file_field.name)[1].lower() == ".mkv":
        response = FileResponse(open(file_field.path, "rb"), as_attachment=True,
                                 filename=f"{project.display_title}.mkv")
        return response
        
    try:
        tmp_mkv = ffmpeg_utils.convert_to_mkv(file_field.path)
        class TemporaryFileResponse(FileResponse):
            def __init__(self, filepath, *args, **kwargs):
                self._temp_filepath = filepath
                super().__init__(open(filepath, "rb"), *args, **kwargs)
                
            def close(self):
                super().close()
                if hasattr(self, "_temp_filepath") and os.path.exists(self._temp_filepath):
                    try:
                        os.remove(self._temp_filepath)
                    except OSError:
                        pass
                        
        response = TemporaryFileResponse(tmp_mkv, as_attachment=True, filename=f"{project.display_title}.mkv")
        return response
    except ffmpeg_utils.FFmpegError:
        messages.error(request, "Failed to convert video container to MKV format.")
        return redirect("project_detail", pk=pk)



def project_status(request, pk):
    """Lightweight JSON endpoint for polling processing status (used by UI spinner)."""
    project = get_object_or_404(VideoProject, pk=pk)
    return JsonResponse({
        "status": project.status,
        "error_message": project.error_message,
        "duration_seconds": project.duration_seconds,
    })


@require_POST
def export_project(request, pk):
    """Unified endpoint to apply all client-side video edits in a single pass."""
    import json
    from django.urls import reverse
    project = get_object_or_404(VideoProject, pk=pk)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    project.status = "processing"
    project.save(update_fields=["status"])

    try:
        # Process from original file to maintain highest quality
        input_path = project.original_file.path
        tmp_output = ffmpeg_utils.process_combined_edits(input_path, data)

        # Generate custom log description
        desc_parts = []
        trim_state = data.get("trim", {})
        if trim_state.get("start") or trim_state.get("end"):
            desc_parts.append(f"Trimmed ({trim_state.get('start', 0.0)}s - {trim_state.get('end', 0.0)}s)")
        if data.get("speed", 1.0) != 1.0:
            desc_parts.append(f"Speed ({data.get('speed')}x)")
        if data.get("effects", {}).get("grayscale"):
            desc_parts.append("Grayscale")
        if data.get("effects", {}).get("rotate"):
            desc_parts.append(f"Rotated ({data.get('effects', {}).get('rotate')}°)")
        if data.get("text_overlays"):
            desc_parts.append(f"Text overlays ({len(data.get('text_overlays'))})")
        if data.get("background_audios"):
            desc_parts.append(f"Bg audio ({len(data.get('background_audios'))})")
            
        description = "Exported: " + ", ".join(desc_parts) if desc_parts else "Exported project edits"

        _apply_new_working_file(project, tmp_output, "export", description)
        messages.success(request, "Video exported successfully with all your edits!")
        return JsonResponse({
            "status": "success", 
            "redirect_url": reverse("project_detail", args=[project.pk])
        })
    except ffmpeg_utils.FFmpegError as e:
        project.status = "error"
        project.error_message = str(e)
        project.save(update_fields=["status", "error_message"])
        return JsonResponse({"status": "error", "error": str(e)}, status=500)


@require_POST
def op_background_audio(request, pk):
    """Mix background audio/sound into the project video with custom volume levels."""
    project = get_object_or_404(VideoProject, pk=pk)

    form = BackgroundAudioForm(request.POST, request.FILES)
    if not form.is_valid():
        for field, errors in form.errors.items():
            for err in errors:
                messages.error(request, f"{field}: {err}")
        return redirect("project_detail", pk=pk)

    project.status = "processing"
    project.save(update_fields=["status"])

    audio_file = form.cleaned_data["audio_file"]
    tmp_dir = os.path.join(settings.MEDIA_ROOT, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    audio_tmp_path = os.path.join(tmp_dir, f"audio_{audio_file.name}")
    with open(audio_tmp_path, "wb") as dest:
        for chunk in audio_file.chunks():
            dest.write(chunk)

    try:
        base_path = project.working_file.path
        bg_vol = form.cleaned_data["bg_volume"]
        vid_vol = form.cleaned_data["video_volume"]
        start_sec = form.cleaned_data.get("start_seconds") or 0.0
        end_sec = form.cleaned_data.get("end_seconds")

        tmp_output = ffmpeg_utils.add_background_audio(
            base_path, audio_tmp_path, bg_vol, vid_vol, start_seconds=start_sec, end_seconds=end_sec
        )
        
        duration = project.duration_seconds or 0.0
        start_val = float(start_sec or 0.0)
        end_val = float(end_sec) if end_sec else duration

        description = (
            f"Added background audio '{audio_file.name}' "
            f"[start={start_val:.2f},end={end_val:.2f}] "
            f"(bg vol: {bg_vol}x, video vol: {vid_vol}x)"
        )
        
        _apply_new_working_file(project, tmp_output, "volume", description)
        messages.success(request, "Background audio added successfully.")
    except ffmpeg_utils.FFmpegError as e:
        project.status = "error"
        project.error_message = str(e)
        project.save(update_fields=["status", "error_message"])
        messages.error(request, "Failed to add background audio. Ensure it is a valid format.")
    finally:
        if os.path.exists(audio_tmp_path):
            try:
                os.remove(audio_tmp_path)
            except OSError:
                pass

    from django.urls import reverse
    return redirect(reverse("project_detail", args=[pk]) + "?tab=audio")


from .models import ProjectAsset

@require_POST
def upload_asset(request, pk):
    """Save an asset file (audio/video) into the ProjectAsset model."""
    project = get_object_or_404(VideoProject, pk=pk)
    
    asset_file = request.FILES.get("asset_file")
    asset_type = request.POST.get("asset_type", "audio")
    
    if not asset_file:
        return JsonResponse({"error": "no_file"}, status=400)
        
    asset = ProjectAsset.objects.create(
        project=project,
        asset_type=asset_type,
        file=asset_file,
        filename=asset_file.name
    )
    
    # Try to extract duration if possible
    try:
        meta = ffmpeg_utils.get_metadata(asset.file.path)
        asset.duration_seconds = meta.get("duration", 0)
        asset.save(update_fields=['duration_seconds'])
    except Exception:
        pass
            
    return JsonResponse({
        "status": "success",
        "asset_id": asset.id,
        "url": asset.file.url,
        "filename": asset.filename,
        "duration": asset.duration_seconds
    })

import json
from django.views.decorators.csrf import csrf_exempt

@require_POST
def save_timeline(request, pk):
    """Save the JSON timeline state for the project."""
    project = get_object_or_404(VideoProject, pk=pk)
    try:
        data = json.loads(request.body)
        project.timeline_state = data
        project.save(update_fields=['timeline_state'])
        return JsonResponse({"status": "success"})
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

@require_POST
def export_timeline(request, pk):
    """Compile the JSON timeline state into a final exported video."""
    project = get_object_or_404(VideoProject, pk=pk)
    try:
        data = json.loads(request.body)
        project.timeline_state = data
        project.save(update_fields=['timeline_state'])
        
        project.status = "processing"
        project.save(update_fields=['status'])
        
        # Dispatch Celery background task
        from .tasks import export_video_task
        export_video_task.delay(project.id, data)
        
        return JsonResponse({"status": "processing"})
        
    except Exception as e:
        project.status = "error"
        project.error_message = str(e)
        project.save(update_fields=['status', 'error_message'])
        return JsonResponse({"error": str(e)}, status=500)


@require_POST
def publish_to_lecture(request, pk):
    """
    Publish the edited VideoProject back to its CameraRecording and set it to published.
    """
    from cameras.models import CameraRecording
    from django.core.files import File
    import os
    
    project = get_object_or_404(VideoProject, pk=pk)
    recording_id = request.GET.get('recording_id')
    
    if not recording_id:
        messages.error(request, "Recording ID missing. Cannot publish.")
        return redirect('project_detail', pk=pk)
        
    recording = get_object_or_404(CameraRecording, id=recording_id)
    
    if not (request.user.is_superuser or recording.teacher == request.user):
        messages.error(request, "Unauthorized to publish this recording.")
        return redirect('project_detail', pk=pk)
        
    try:
        # Overwrite the original recording video_file with the project's working_file
        edited_path = project.working_file.path
        filename = os.path.basename(edited_path)
        
        # Save a copy to the recording so the VideoProject is unaffected
        with open(edited_path, 'rb') as f:
            recording.video_file.save(filename, File(f), save=False)
            
        recording.is_published = True
        recording.recording_status = 'completed'
        
        # Update duration if available
        try:
            if project.duration_seconds:
                from datetime import timedelta
                recording.duration = timedelta(seconds=project.duration_seconds)
        except Exception:
            pass
            
        recording.save()
        
        messages.success(request, f"Lecture '{recording.title}' has been successfully published!")
        return redirect('manage_recordings')
        
    except Exception as e:
        messages.error(request, f"Failed to publish lecture: {str(e)}")
        return redirect(f"{reverse('project_detail', args=[pk])}?recording_id={recording_id}")
