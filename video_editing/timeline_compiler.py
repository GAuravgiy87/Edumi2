import os
import subprocess
from django.conf import settings
from .ffmpeg_utils import FFmpegError

def compile_timeline_to_ffmpeg(project, timeline_json, output_path):
    """
    Takes a JSON timeline state and compiles it into a complex FFmpeg filtergraph
    to render the final video.
    """
    from cameras.ffmpeg_helpers import get_ffmpeg_binary
    ffmpeg_bin = get_ffmpeg_binary()

    # Step 1: Gather inputs
    inputs = []
    # Index 0 is always the original project file
    inputs.append(project.original_file.path)
    
    cmd = [ffmpeg_bin, '-y']
    for inp in inputs:
        cmd.extend(['-i', inp])

    filter_complex = []
    video_outs = []
    audio_outs = []
    
    # Get video track from timeline
    v_track = next((t for t in timeline_json.get('tracks', []) if t.get('type') == 'video'), None)
    
    if not v_track or not v_track.get('clips'):
        # Fallback to copy if no timeline
        cmd = [ffmpeg_bin, '-y', '-i', inputs[0], '-c', 'copy', output_path]
        subprocess.run(cmd, check=True)
        return
        
    clips = v_track['clips']
    
    # For each clip, trim it
    for i, clip in enumerate(clips):
        trim_start = clip.get('trimStart', 0)
        trim_end = clip.get('trimEnd', clip.get('end', 10))
        
        v_label = f"[v{i}]"
        a_label = f"[a{i}]"
        
        # trim video
        filter_complex.append(f"[0:v]trim=start={trim_start}:end={trim_end},setpts=PTS-STARTPTS{v_label}")
        # trim audio
        filter_complex.append(f"[0:a]atrim=start={trim_start}:end={trim_end},asetpts=PTS-STARTPTS{a_label}")
        
        video_outs.append(v_label)
        audio_outs.append(a_label)
        
    # Concat clips if more than one
    current_v = None
    current_a = None
    if len(clips) > 1:
        concat_inputs = "".join(video_outs + audio_outs)
        n = len(clips)
        filter_complex.append(f"{concat_inputs}concat=n={n}:v=1:a=1[v_concat][a_concat]")
        current_v = "[v_concat]"
        current_a = "[a_concat]"
    elif len(clips) == 1:
        current_v = video_outs[0]
        current_a = audio_outs[0]
    else:
        current_v = "[0:v]"
        current_a = "[0:a]"

    # Overlay Text if any
    t_track = next((t for t in timeline_json.get('tracks', []) if t.get('type') == 'text'), None)
    if t_track and t_track.get('clips'):
        for i, text_clip in enumerate(t_track['clips']):
            text_str = text_clip.get('text', '').replace("'", "").replace(":", r"\:")
            position = text_clip.get('position', 'bottom')
            if position == 'top':
                x = '(w-text_w)/2'
                y = 'h*0.1'
            elif position == 'center':
                x = '(w-text_w)/2'
                y = '(h-text_h)/2'
            else: # bottom
                x = '(w-text_w)/2'
                y = 'h-text_h-h*0.1'
                
            fontsize = text_clip.get('fontsize', 48)
            fontcolor = text_clip.get('color', 'white')
            start = text_clip.get('start', 0)
            end = text_clip.get('end', 10)
            
            enable_str = f"between(t,{start},{end})"
            next_v = f"[v_txt{i}]"
            
            drawtext_filter = (f"{current_v}drawtext=text='{text_str}':x={x}:y={y}:"
                               f"fontsize={fontsize}:fontcolor={fontcolor}:enable='{enable_str}'{next_v}")
            filter_complex.append(drawtext_filter)
            current_v = next_v
            
    # Resolution scaling based on exportResolution
    resolution = timeline_json.get('exportResolution', '1080p')
    scale_label = "[v_scaled]"
    if resolution == '480p':
        filter_complex.append(f"{current_v}scale=-2:480{scale_label}")
        current_v = scale_label
    elif resolution == '720p':
        filter_complex.append(f"{current_v}scale=-2:720{scale_label}")
        current_v = scale_label
    elif resolution == '1440p':
        filter_complex.append(f"{current_v}scale=-2:1440{scale_label}")
        current_v = scale_label
    elif resolution == '4k':
        filter_complex.append(f"{current_v}scale=-2:2160{scale_label}")
        current_v = scale_label
    else: # default 1080p
        filter_complex.append(f"{current_v}scale=-2:1080{scale_label}")
        current_v = scale_label

    if filter_complex:
        cmd.extend(['-filter_complex', ";".join(filter_complex)])
        cmd.extend(['-map', current_v, '-map', current_a])
    else:
        cmd.extend(['-c', 'copy'])
        
    # Bitrate/Quality settings based on exportQuality
    quality = timeline_json.get('exportQuality', 'high')
    if quality == 'low':
        cmd.extend(['-crf', '28'])
    elif quality == 'medium':
        cmd.extend(['-crf', '23'])
    elif quality == 'ultra':
        cmd.extend(['-crf', '14'])
    else: # high (default)
        cmd.extend(['-crf', '18'])
        
    cmd.append(output_path)
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="ignore")
        raise FFmpegError(stderr[-3000:])
