"""
FFmpeg processing utilities for video editing
"""
import os
import subprocess
from django.conf import settings

from video_editing.models import VideoEditSession


def process_video_edits(session):
    """Process all edit actions and return the path to the edited video."""
    input_path = session.original_video.original_file.path
    current_input = input_path

    for action in session.actions.all():
        temp_output = os.path.join(settings.MEDIA_ROOT, f'temp_edit_{session.id}_{action.id}.mp4')

        if action.action_type == 'trim':
            trim_video(current_input, temp_output, action.parameters['start_time'], action.parameters['end_time'])
        elif action.action_type == 'mute':
            mute_video_section(current_input, temp_output, action.parameters['start_time'], action.parameters['end_time'])
        elif action.action_type == 'split':
            # For split, we just take the first part for simplicity (can be expanded)
            trim_video(current_input, temp_output, 0, action.parameters['split_point'])
        elif action.action_type == 'rotate':
            rotate_video(current_input, temp_output, action.parameters['degrees'])
        elif action.action_type == 'add_text':
            add_text_overlay(current_input, temp_output, action.parameters)
        elif action.action_type == 'add_audio':
            add_audio_overlay(current_input, temp_output, action.audio_file.path if action.audio_file else None, action.parameters)
        elif action.action_type == 'replace_audio':
            replace_audio(current_input, temp_output, action.audio_file.path if action.audio_file else None, action.parameters)

        # Clean up previous temp file
        if current_input != input_path and os.path.exists(current_input):
            os.remove(current_input)

        current_input = temp_output

    return current_input


def trim_video(input_path, output_path, start_time, end_time):
    """Trim a video using FFmpeg."""
    subprocess.run([
        'ffmpeg',
        '-i', input_path,
        '-ss', str(start_time),
        '-to', str(end_time),
        '-c', 'copy',
        '-y',
        output_path
    ], capture_output=True, check=True)


def mute_video_section(input_path, output_path, start_time, end_time):
    """Mute a section of a video using FFmpeg."""
    # Use FFmpeg filter to mute audio between start and end times
    subprocess.run([
        'ffmpeg',
        '-i', input_path,
        '-af', f"volume=enable='between(t,{start_time},{end_time})':volume=0",
        '-c:v', 'copy',
        '-y',
        output_path
    ], capture_output=True, check=True)


def rotate_video(input_path, output_path, degrees):
    """Rotate a video using FFmpeg."""
    # Map degrees to FFmpeg transpose values
    transpose_filters = {
        90: 'transpose=1',
        180: 'transpose=2,transpose=2',
        270: 'transpose=2'
    }
    transpose = transpose_filters.get(degrees, 'transpose=1')

    subprocess.run([
        'ffmpeg',
        '-i', input_path,
        '-vf', transpose,
        '-c:a', 'copy',
        '-y',
        output_path
    ], capture_output=True, check=True)


def add_text_overlay(input_path, output_path, params):
    """Add text overlay to video using FFmpeg."""
    text = params['text'].replace("'", "\\'")
    font_size = params['font_size']
    color = params['color'].replace('#', '')
    position = params['position']
    start_time = params['start_time']
    end_time = params['end_time']

    # Position mapping
    position_map = {
        'center': 'x=(w-text_w)/2:y=(h-text_h)/2',
        'top': 'x=(w-text_w)/2:y=50',
        'bottom': 'x=(w-text_w)/2:y=h-text_h-50',
        'top_left': 'x=50:y=50',
        'top_right': 'x=w-text_w-50:y=50',
        'bottom_left': 'x=50:y=h-text_h-50',
        'bottom_right': 'x=w-text_w-50:y=h-text_h-50'
    }

    pos = position_map.get(position, 'x=(w-text_w)/2:y=(h-text_h)/2')

    drawtext_filter = (
        f"drawtext=text='{text}':fontsize={font_size}:fontcolor=0x{color}:{pos}"
        f":enable='between(t,{start_time},{end_time})'"
    )

    subprocess.run([
        'ffmpeg',
        '-i', input_path,
        '-vf', drawtext_filter,
        '-c:a', 'copy',
        '-y',
        output_path
    ], capture_output=True, check=True)


def add_audio_overlay(input_path, output_path, audio_path, params):
    """Add audio overlay to video using FFmpeg."""
    if not audio_path:
        # If no audio file, just copy
        os.rename(input_path, output_path)
        return

    start_time = params.get('start_time', 0)
    volume = params.get('volume', 100) / 100.0

    subprocess.run([
        'ffmpeg',
        '-i', input_path,
        '-i', audio_path,
        '-filter_complex', f"[1:a]volume={volume},adelay={start_time*1000}|{start_time*1000}[aud];[0:a][aud]amix=inputs=2:duration=first",
        '-c:v', 'copy',
        '-y',
        output_path
    ], capture_output=True, check=True)


def replace_audio(input_path, output_path, audio_path, params):
    """Replace video audio using FFmpeg."""
    if not audio_path:
        # If no audio file, just copy
        os.rename(input_path, output_path)
        return

    volume = params.get('volume', 100) / 100.0

    subprocess.run([
        'ffmpeg',
        '-i', input_path,
        '-i', audio_path,
        '-filter_complex', f"[1:a]volume={volume}[aud]",
        '-c:v', 'copy',
        '-map', '0:v',
        '-map', '[aud]',
        '-shortest',
        '-y',
        output_path
    ], capture_output=True, check=True)
