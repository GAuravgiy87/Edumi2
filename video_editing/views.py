import os
import shutil
import uuid
import json
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.http import FileResponse, JsonResponse, HttpResponseForbidden, StreamingHttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from . import ffmpeg_utils
from .forms import (
    VideoUploadForm, TrimForm, VolumeForm, MergeForm,
    TextOverlayForm, SpeedForm, RotateForm, ResizeForm, FadeForm,
    BackgroundAudioForm,
)
from .models import VideoProject, EditOperation, ProjectAsset


def serve_media_ranges(request, path):
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if not os.path.exists(file_path):
        raise Http404("File not found")

    file_size = os.path.getsize(file_path)
    range_header = request.META.get('HTTP_RANGE', '').strip()
    
    def file_iterator(fn, offset, length):
        with open(fn, 'rb') as f:
            f.seek(offset)
            remaining = length
            while remaining > 0:
                chunk_size = min(remaining, 65536)
                data = f.read(chunk_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    if range_header:
        match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            start = int(match.group(1))
            end = match.group(2)
            end = int(end) if end else file_size - 1
            
            if start >= file_size:
                return StreamingHttpResponse(status=416)
                
            length = end - start + 1
            response = StreamingHttpResponse(file_iterator(file_path, start, length), status=206, content_type='video/mp4')
            response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response['Accept-Ranges'] = 'bytes'
            response['Content-Length'] = str(length)
            return response

    response = StreamingHttpResponse(file_iterator(file_path, 0, file_size), content_type='video/mp4')
    response['Accept-Ranges'] = 'bytes'
    response['Content-Length'] = str(file_size)
    return response


# ---------------------------------------------------------------------------
# Project list / upload
# ---------------------------------------------------------------------------

@login_required
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
                
                # Initialize clips_json
                orig_filename = os.path.basename(project.original_file.name)
                if len(orig_filename) > 32:
                    orig_filename = project.title + ".mp4"
                project.clips_json = json.dumps([
                    {"title": orig_filename, "duration": meta["duration"]}
                ])
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


def _get_owned_project(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)
    if project.owner_id != request.user.id:
        return None
    return project


@login_required
def project_detail(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden("You do not have access to this project.")

    # Ensure clips_json is initialized for existing projects
    if not project.clips_json or project.clips_json.strip() == "":
        orig_filename = os.path.basename(project.original_file.name)
        if len(orig_filename) > 32:
            orig_filename = project.title + ".mp4"
        project.clips_json = json.dumps([
            {"title": orig_filename, "duration": float(project.duration_seconds or 0.0)}
        ])
        project.save(update_fields=["clips_json"])

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
        "operations": project.operations.filter(active=True)[:20],
        "has_redo": project.operations.filter(active=False).exists(),
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
        # Clear Redo stack on new action
        inactive_ops = project.operations.filter(active=False)
        for inactive in list(inactive_ops):
            inactive.delete()

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
            
            # Clamp trim bounds to new duration
            if project.trim_start > project.duration_seconds:
                project.trim_start = 0.0
            if project.trim_end is not None and project.trim_end > project.duration_seconds:
                project.trim_end = project.duration_seconds
        finally:
            project.save()

        op = EditOperation(
            project=project,
            operation_type=operation_type,
            description=description,
            trim_start=project.trim_start,
            trim_end=project.trim_end,
        )
        if tmp_output_path and os.path.exists(tmp_output_path):
            try:
                filename = os.path.basename(tmp_output_path)
                with open(tmp_output_path, "rb") as f:
                    op.video_file.save(filename, File(f), save=False)
            except Exception:
                pass
        op.save()
    finally:
        if os.path.exists(tmp_output_path):
            try:
                os.remove(tmp_output_path)
            except OSError:
                pass


def _insert_clip_to_sequence(project, asset_title, asset_duration, timestamp):
    try:
        clips = json.loads(project.clips_json) if project.clips_json else []
    except Exception:
        clips = []
    
    if not clips:
        orig_filename = project.title + ".mp4"
        clips = [{"title": orig_filename, "duration": project.duration_seconds or 0.0}]

    new_clips = []
    current_time = 0.0
    inserted = False
    
    for clip in clips:
        clip_dur = float(clip.get("duration", 0.0))
        clip_title = clip.get("title", "Clip")
        
        if inserted:
            new_clips.append(clip)
            continue
            
        if current_time <= timestamp < (current_time + clip_dur):
            # Split point is within this clip!
            split_offset = timestamp - current_time
            if split_offset <= 0.05:
                # Insert before this clip
                new_clips.append({"title": asset_title, "duration": asset_duration})
                new_clips.append(clip)
            elif (clip_dur - split_offset) <= 0.05:
                # Insert after this clip
                new_clips.append(clip)
                new_clips.append({"title": asset_title, "duration": asset_duration})
            else:
                # Split this clip!
                new_clips.append({"title": clip_title, "duration": round(split_offset, 2)})
                new_clips.append({"title": asset_title, "duration": asset_duration})
                new_clips.append({"title": clip_title, "duration": round(clip_dur - split_offset, 2)})
            inserted = True
        else:
            new_clips.append(clip)
            current_time += clip_dur
            
    if not inserted:
        # Append to the end
        new_clips.append({"title": asset_title, "duration": asset_duration})
        
    project.clips_json = json.dumps(new_clips)
    project.save(update_fields=["clips_json"])


def _handle_operation(request, pk, form_class, run_ffmpeg_fn, operation_type,
                       describe_fn, extra_files=None):
    """
    Shared plumbing for all edit endpoints:
    1. Validate form
    2. Run the ffmpeg function against the current working file
    3. Save the result, log it, redirect back to project detail
    """
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden("You do not have access to this project.")

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

@login_required
@require_POST
def op_split(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden("You do not have access")

    split_time_str = request.POST.get("split_at", "0.0")
    try:
        split_time = float(split_time_str)
    except ValueError:
        split_time = 0.0
        messages.warning(request, "Invalid split time, using 0.0")

    project.status = "processing"
    project.save(update_fields=["status"])

    try:
        # Parse clips_json, ensure it's a list
        if not project.clips_json or project.clips_json.strip() == "":
            clips = []
        else:
            try:
                clips = json.loads(project.clips_json)
                if not isinstance(clips, list):
                    clips = []
            except Exception:
                clips = []
                
        # If no clips, initialize with original
        if not clips:
            orig_filename = os.path.basename(project.original_file.name)
            if len(orig_filename) > 32:
                orig_filename = project.title + ".mp4"
            clips = [{"title": orig_filename, "duration": float(project.duration_seconds or 0.0)}]
            
        new_clips = []
        current_time = 0.0
        found = False
        for clip in clips:
            clip_duration = float(clip.get("duration", 0.0))
            if not found and current_time <= split_time < (current_time + clip_duration):
                first_part_duration = split_time - current_time
                second_part_duration = clip_duration - first_part_duration
                new_clips.append({
                    "title": clip.get("title", "Clip"), 
                    "duration": round(first_part_duration, 4)
                })
                new_clips.append({
                    "title": clip.get("title", "Clip"), 
                    "duration": round(second_part_duration, 4)
                })
                found = True
            else:
                new_clips.append(clip)
            current_time += clip_duration
        
        # Update project
        project.clips_json = json.dumps(new_clips)
        project.status = "ready"
        project.error_message = ""  # Clear any error
        project.save()
        
        EditOperation.objects.create(
            project=project,
            operation_type="trim",  # Use existing type
            description=f"Split video at {split_time:.2f}s"
        )
        messages.success(request, f"Split video successfully at {split_time:.2f} seconds!")

    except Exception as e:
        print(f"Error in op_split: {str(e)}")  # For server logs
        project.status = "error"
        project.error_message = str(e)
        project.save(update_fields=["status", "error_message"])
        messages.error(request, f"Failed to split video: {str(e)}")

    from django.urls import reverse
    return redirect(reverse("project_detail", args=[pk]))


@login_required
@require_POST
def op_trim(request, pk):
    def run_trim(path, form):
        trim_mode = form.cleaned_data.get("trim_mode") or "extract"
        start = form.cleaned_data["start_seconds"]
        end = form.cleaned_data["end_seconds"]
        if trim_mode == "delete":
            return ffmpeg_utils.delete_range(path, start, end)
        return ffmpeg_utils.trim(path, start, end)

    def describe_trim(form):
        trim_mode = form.cleaned_data.get("trim_mode") or "extract"
        start = form.cleaned_data["start_seconds"]
        end = form.cleaned_data["end_seconds"]
        if trim_mode == "delete":
            return f"Cut out middle section {start}s - {end}s"
        return f"Trimmed to {start}s - {end}s"

    return _handle_operation(
        request, pk, TrimForm,
        run_ffmpeg_fn=run_trim,
        operation_type="trim",
        describe_fn=describe_trim,
    )


@login_required
@require_POST
def op_mute(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden()
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


@login_required
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


@login_required
@require_POST
def op_merge(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden()

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

        # Update clips_json
        try:
            meta_clip = ffmpeg_utils.get_metadata(clip_tmp_path)
            clip_dur = meta_clip.get("duration", 0.0)
            clips = json.loads(project.clips_json) if project.clips_json else []
            if position == "start":
                clips.insert(0, {"title": clip_file.name, "duration": clip_dur})
            else:
                clips.append({"title": clip_file.name, "duration": clip_dur})
            project.clips_json = json.dumps(clips)
            project.save(update_fields=["clips_json"])
        except Exception:
            pass

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


@login_required
@require_POST
def op_text_overlay(request, pk):
    project = _get_owned_project(request, pk)
    duration = project.duration_seconds if project else 0.0

    def run(path, form):
        d = form.cleaned_data
        import sys
        print("DEBUG: form cleaned data in op_text_overlay:", d, file=sys.stderr)
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


@login_required
@require_POST
def op_speed(request, pk):
    return _handle_operation(
        request, pk, SpeedForm,
        run_ffmpeg_fn=lambda path, form: ffmpeg_utils.change_speed(path, form.cleaned_data["speed_factor"]),
        operation_type="speed",
        describe_fn=lambda form: f"Changed speed to {form.cleaned_data['speed_factor']}x",
    )


@login_required
@require_POST
def op_rotate(request, pk):
    return _handle_operation(
        request, pk, RotateForm,
        run_ffmpeg_fn=lambda path, form: ffmpeg_utils.rotate(path, int(form.cleaned_data["degrees"])),
        operation_type="rotate",
        describe_fn=lambda form: f"Rotated {form.cleaned_data['degrees']}°",
    )


@login_required
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


@login_required
@require_POST
def op_grayscale(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden()
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


@login_required
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


@login_required
@require_POST
def op_reset(request, pk):
    """Discard all edits and revert current_file back to the original upload."""
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden()

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
    
    # Reset clips_json
    orig_filename = os.path.basename(project.original_file.name)
    if len(orig_filename) > 32:
        orig_filename = project.title + ".mp4"
    project.clips_json = json.dumps([
        {"title": orig_filename, "duration": meta["duration"]}
    ])
    project.save()

    EditOperation.objects.create(project=project, operation_type="reset", description="Reset to original upload")
    messages.success(request, "Project reset to the original uploaded video.")
    return redirect("project_detail", pk=pk)


@login_required
@require_POST
def op_revert(request, pk, op_pk):
    """Revert the project back to the state after a specific EditOperation."""
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden("You do not have access to this project.")

    op = get_object_or_404(EditOperation, pk=op_pk, project=project)

    # Mark all operations newer than the one we are reverting to as inactive
    newer_ops = project.operations.filter(pk__gt=op.pk)
    newer_ops.update(active=False)

    # Revert project.current_file to a copy of op.video_file
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

    if op.video_file and op.video_file.name:
        try:
            filename = os.path.basename(op.video_file.name)
            with open(op.video_file.path, "rb") as f:
                project.current_file.save(filename, File(f), save=False)
        except Exception as e:
            messages.error(request, f"Failed to restore file: {str(e)}")
            return redirect("project_detail", pk=pk)
    else:
        project.current_file = None

    # Refresh metadata
    try:
        meta = ffmpeg_utils.get_metadata(project.working_file.path)
        project.duration_seconds = meta["duration"]
        project.width = meta["width"]
        project.height = meta["height"]
        project.has_audio = meta["has_audio"]
        project.status = "ready"
        project.error_message = ""
        project.trim_start = op.trim_start
        project.trim_end = op.trim_end
    except Exception as e:
        project.status = "error"
        project.error_message = str(e)
    finally:
        project.save()

    messages.success(request, f"Reverted project to state: {op.description}")
    return redirect("project_detail", pk=pk)


@login_required
@require_POST
def op_redo(request, pk):
    """Redo the last undone operation."""
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden("You do not have access to this project.")

    next_op = project.operations.filter(active=False).order_by('pk').first()
    if not next_op:
        messages.error(request, "Nothing to redo.")
        return redirect("project_detail", pk=pk)

    next_op.active = True
    next_op.save(update_fields=['active'])

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

    if next_op.video_file and next_op.video_file.name:
        try:
            filename = os.path.basename(next_op.video_file.name)
            with open(next_op.video_file.path, "rb") as f:
                project.current_file.save(filename, File(f), save=False)
        except Exception as e:
            messages.error(request, f"Failed to redo operation: {str(e)}")
            return redirect("project_detail", pk=pk)
    else:
        project.current_file = None

    try:
        meta = ffmpeg_utils.get_metadata(project.working_file.path)
        project.duration_seconds = meta["duration"]
        project.width = meta["width"]
        project.height = meta["height"]
        project.has_audio = meta["has_audio"]
        project.status = "ready"
        project.error_message = ""
        project.trim_start = next_op.trim_start
        project.trim_end = next_op.trim_end
    except Exception as e:
        project.status = "error"
        project.error_message = str(e)
    finally:
        project.save()

    messages.success(request, f"Redid operation: {next_op.description}")
    return redirect("project_detail", pk=pk)


@login_required
@require_POST
def project_delete(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden()
    title = project.display_title
    for f in [project.original_file, project.current_file]:
        if f and f.name and os.path.exists(f.path):
            try:
                os.remove(f.path)
            except OSError:
                pass
    project.delete()
    messages.success(request, f"Project '{title}' deleted.")
    return redirect("project_list")


@login_required
def project_download(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden()
    file_field = project.working_file
    response = FileResponse(open(file_field.path, "rb"), as_attachment=True,
                             filename=f"{project.display_title}{os.path.splitext(file_field.name)[1]}")
    return response


@login_required
def project_download_mkv(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden()
    
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


@login_required
def project_status(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return JsonResponse({"error": "forbidden"}, status=403)
    return JsonResponse({
        "status": project.status,
        "error_message": project.error_message,
        "duration_seconds": project.duration_seconds,
    })


@login_required
@require_POST
def export_project(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return JsonResponse({"error": "forbidden"}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    project.status = "processing"
    project.save(update_fields=["status"])

    try:
        input_path = project.original_file.path
        tmp_output = ffmpeg_utils.process_combined_edits(input_path, data)

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
        from django.urls import reverse
        return JsonResponse({
            "status": "success", 
            "redirect_url": reverse("project_detail", args=[project.pk])
        })
    except ffmpeg_utils.FFmpegError as e:
        project.status = "error"
        project.error_message = str(e)
        project.save(update_fields=["status", "error_message"])
        return JsonResponse({"status": "error", "error": str(e)}, status=500)


@login_required
@require_POST
def op_background_audio(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden("You do not have access to this project.")

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


@login_required
@require_POST
def upload_audio_temp(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return JsonResponse({"error": "forbidden"}, status=403)
        
    audio_file = request.FILES.get("audio_file")
    if not audio_file:
        return JsonResponse({"error": "no_file"}, status=400)
        
    tmp_dir = os.path.join(settings.MEDIA_ROOT, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    audio_tmp_path = os.path.join(tmp_dir, f"audio_{uuid.uuid4().hex}_{audio_file.name}")
    
    with open(audio_tmp_path, "wb") as dest:
        for chunk in audio_file.chunks():
            dest.write(chunk)
            
    return JsonResponse({
        "status": "success",
        "temp_path": audio_tmp_path,
        "filename": audio_file.name
    })


@login_required
@require_POST
def upload_asset(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return JsonResponse({"error": "Forbidden"}, status=403)

    video_file = request.FILES.get("video_file")
    if not video_file:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    asset = ProjectAsset.objects.create(
        project=project,
        file=video_file,
        title=video_file.name,
        filename=video_file.name
    )

    try:
        meta = ffmpeg_utils.get_metadata(asset.file.path)
        asset.duration_seconds = meta.get("duration", 0.0)
        asset.save(update_fields=["duration_seconds"])
    except Exception:
        pass

    return JsonResponse({
        "success": True,
        "asset": {
            "id": asset.id,
            "url": asset.file.url,
            "title": asset.display_title,
            "duration": asset.display_duration
        }
    })


@login_required
@require_POST
def insert_asset(request, pk):
    project = _get_owned_project(request, pk)
    if project is None:
        return HttpResponseForbidden()

    asset_id = request.POST.get("asset_id")
    timestamp_str = request.POST.get("timestamp")
    
    asset = get_object_or_404(ProjectAsset, id=asset_id, project=project)
    
    try:
        timestamp = float(timestamp_str) if timestamp_str else 0.0
    except ValueError:
        timestamp = 0.0

    project.status = "processing"
    project.save(update_fields=["status"])

    try:
        base_path = project.working_file.path
        clip_path = asset.file.path
        
        duration = project.duration_seconds or 0.0
        if timestamp <= 0.1:
            tmp_output = ffmpeg_utils.merge([clip_path, base_path])
            description = f"Inserted clip '{asset.display_title}' at the beginning"
        elif timestamp >= (duration - 0.1):
            tmp_output = ffmpeg_utils.merge([base_path, clip_path])
            description = f"Inserted clip '{asset.display_title}' at the end"
        else:
            part_a = ffmpeg_utils.trim(base_path, 0.0, timestamp)
            part_b = ffmpeg_utils.trim(base_path, timestamp, duration)
            tmp_output = ffmpeg_utils.merge([part_a, clip_path, part_b])
            for p in [part_a, part_b]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            description = f"Inserted clip '{asset.display_title}' at {timestamp:.2f}s"

        _apply_new_working_file(project, tmp_output, "merge", description)
        
        try:
            _insert_clip_to_sequence(project, asset.display_title, asset.duration_seconds or 0.0, timestamp)
        except Exception:
            pass

        messages.success(request, "Clip inserted into timeline successfully.")
    except ffmpeg_utils.FFmpegError as e:
        project.status = "error"
        project.error_message = str(e)
        project.save(update_fields=["status", "error_message"])
        messages.error(request, f"Failed to insert clip: {e}")
    
    return redirect("project_detail", pk=pk)


@login_required
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
        edited_path = project.working_file.path
        filename = os.path.basename(edited_path)
        
        with open(edited_path, 'rb') as f:
            recording.video_file.save(filename, File(f), save=False)
            
        recording.is_published = True
        recording.recording_status = 'completed'
        
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


# Keep Celery save_timeline / export_timeline stubs for safety
@login_required
@require_POST
def save_timeline(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)
    try:
        data = json.loads(request.body)
        project.timeline_state = data
        project.save(update_fields=['timeline_state'])
        return JsonResponse({"status": "success"})
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


@login_required
@require_POST
def export_timeline(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)
    try:
        data = json.loads(request.body)
        project.timeline_state = data
        project.save(update_fields=['timeline_state'])
        project.status = "processing"
        project.save(update_fields=['status'])
        from .tasks import export_video_task
        export_video_task.delay(project.id, data)
        return JsonResponse({"status": "processing"})
    except Exception as e:
        project.status = "error"
        project.error_message = str(e)
        project.save(update_fields=['status', 'error_message'])
        return JsonResponse({"error": str(e)}, status=500)
