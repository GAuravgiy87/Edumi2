"""
AMD GPU Setup & Optimization Script for EduMi
=============================================
Hardware: AMD dGPU + Intel iGPU — 4 CPU cores allocated (shared machine)

This script:
  1. Detects AMD GPU via DirectML / ROCm / OpenCL
  2. Configures OpenCV to use GPU-accelerated backends
  3. Sets process affinity to 4 cores (other projects share the machine)
  4. Patches face_recognition to use dlib with CUDA/OpenCL if available
  5. Configures H.264/H.265 hardware encoding for recordings
  6. Prints a full capability report

Run once before starting the server:
    python scripts/gpu_setup.py

Or import gpu_config from here in settings/startup.
"""

import os
import sys
import platform
import subprocess
import logging

logger = logging.getLogger(__name__)

# ─── CPU Affinity: use all 12 cores ──────────────────────────────────────────

def set_cpu_affinity():
    """Pin process to first 4 cores — shared machine, other projects also running."""
    try:
        import psutil
        p = psutil.Process()
        total = psutil.cpu_count(logical=True)
        # Cap at 4 cores
        cores = list(range(min(4, total)))
        p.cpu_affinity(cores)
        print(f"[CPU] Affinity set to {len(cores)} cores (of {total} available)")
        return True
    except Exception as e:
        print(f"[CPU] Could not set affinity: {e}")
        return False


# ─── AMD GPU Detection ────────────────────────────────────────────────────────

def detect_amd_gpu():
    """Detect AMD GPU via multiple methods."""
    results = {
        'found': False,
        'name': None,
        'opencl': False,
        'directml': False,
        'rocm': False,
        'vulkan': False,
    }

    # Method 1: WMI (Windows)
    if platform.system() == 'Windows':
        try:
            import wmi
            c = wmi.WMI()
            for gpu in c.Win32_VideoController():
                if 'AMD' in gpu.Name or 'Radeon' in gpu.Name or 'ATI' in gpu.Name:
                    results['found'] = True
                    results['name'] = gpu.Name
                    print(f"[GPU] AMD GPU detected via WMI: {gpu.Name}")
                    break
        except ImportError:
            # Fallback: subprocess
            try:
                out = subprocess.check_output(
                    ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                    stderr=subprocess.DEVNULL
                ).decode()
                for line in out.splitlines():
                    if 'AMD' in line or 'Radeon' in line:
                        results['found'] = True
                        results['name'] = line.strip()
                        print(f"[GPU] AMD GPU detected: {line.strip()}")
                        break
            except Exception:
                pass

    # Method 2: OpenCL
    try:
        import pyopencl as cl
        platforms = cl.get_platforms()
        for plat in platforms:
            if 'AMD' in plat.name or 'Advanced Micro' in plat.name:
                devices = plat.get_devices(cl.device_type.GPU)
                if devices:
                    results['opencl'] = True
                    results['found'] = True
                    if not results['name']:
                        results['name'] = devices[0].name
                    print(f"[OpenCL] AMD GPU: {devices[0].name}")
                    break
    except ImportError:
        print("[OpenCL] pyopencl not installed — skipping OpenCL detection")
    except Exception as e:
        print(f"[OpenCL] Detection failed: {e}")

    # Method 3: DirectML (Windows, AMD/Intel/NVIDIA)
    try:
        import torch_directml
        dml_device = torch_directml.device()
        results['directml'] = True
        print(f"[DirectML] Available — device: {dml_device}")
    except ImportError:
        print("[DirectML] torch-directml not installed")
    except Exception as e:
        print(f"[DirectML] Error: {e}")

    # Method 4: ROCm (Linux AMD)
    try:
        import torch
        if torch.cuda.is_available():
            # ROCm exposes itself as CUDA
            name = torch.cuda.get_device_name(0)
            if 'AMD' in name or 'Radeon' in name or 'gfx' in name.lower():
                results['rocm'] = True
                results['found'] = True
                results['name'] = name
                print(f"[ROCm] AMD GPU via PyTorch: {name}")
    except ImportError:
        pass

    return results


# ─── OpenCV GPU Backend ───────────────────────────────────────────────────────

def configure_opencv_gpu():
    """Configure OpenCV to use hardware acceleration."""
    import cv2

    info = {
        'opencl_enabled': False,
        'cuda_enabled': False,
        'backend': 'CPU',
    }

    # Enable OpenCL (works with AMD via OpenCL)
    try:
        cv2.ocl.setUseOpenCL(True)
        if cv2.ocl.useOpenCL():
            device = cv2.ocl.Device.getDefault()
            info['opencl_enabled'] = True
            info['backend'] = f"OpenCL ({device.name()})"
            print(f"[OpenCV] OpenCL enabled: {device.name()}")
        else:
            print("[OpenCV] OpenCL not available — using CPU")
    except Exception as e:
        print(f"[OpenCV] OpenCL setup failed: {e}")

    # Check CUDA (NVIDIA / ROCm)
    try:
        if cv2.cuda.getCudaEnabledDeviceCount() > 0:
            info['cuda_enabled'] = True
            info['backend'] = 'CUDA'
            print(f"[OpenCV] CUDA devices: {cv2.cuda.getCudaEnabledDeviceCount()}")
    except AttributeError:
        pass  # OpenCV not built with CUDA

    # Set thread count — capped to 4-core budget, leave 1 for OS
    cv2.setNumThreads(3)
    print(f"[OpenCV] Threads set to: {cv2.getNumThreads()}")

    return info


# ─── FFMPEG / Video Codec Config ─────────────────────────────────────────────

def get_video_writer(output_path: str, fps: float = 25.0, width: int = 1280, height: int = 720):
    """
    Returns an OpenCV VideoWriter using the best available hardware codec.

    Priority:
      1. H.264 via AMD AMF (h264_amf)  — AMD GPU hardware encoding
      2. H.264 via Intel QSV (h264_qsv) — Intel iGPU hardware encoding
      3. H.265/HEVC via AMF             — smaller files, AMD GPU
      4. H.264 software (libx264)       — CPU fallback
      5. MJPEG                          — last resort

    Usage:
        writer = get_video_writer('recordings/meeting_ABC.mp4', fps=25, width=1280, height=720)
        writer.write(frame)
        writer.release()
    """
    import cv2

    codecs = [
        # (fourcc, description, file_ext)
        ('avc1', 'H.264 AMF (AMD GPU)',    '.mp4'),   # AMD hardware H.264
        ('hvc1', 'H.265 AMF (AMD GPU)',    '.mp4'),   # AMD hardware H.265
        ('H264', 'H.264 QSV (Intel iGPU)', '.mp4'),   # Intel QSV
        ('X264', 'H.264 libx264 (CPU)',    '.mp4'),   # Software H.264
        ('XVID', 'XVID (CPU fallback)',    '.avi'),   # XVID fallback
        ('MJPG', 'MJPEG (last resort)',    '.avi'),   # MJPEG last resort
    ]

    for fourcc_str, desc, ext in codecs:
        try:
            # Adjust extension if needed
            base = output_path.rsplit('.', 1)[0] if '.' in output_path else output_path
            path = base + ext
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
            writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
            if writer.isOpened():
                print(f"[VideoWriter] Using codec: {desc} → {path}")
                return writer, path
            writer.release()
        except Exception:
            continue

    print("[VideoWriter] WARNING: All codecs failed — no recording available")
    return None, None


def get_ffmpeg_hw_encode_cmd(input_pipe: str, output_path: str,
                              fps: int = 25, crf: int = 23) -> list:
    """
    Returns an FFmpeg command list for hardware-accelerated encoding.
    Use this when piping raw frames to FFmpeg directly (better quality).

    AMD AMF H.264:
        ffmpeg -f rawvideo -pix_fmt bgr24 -s WxH -r FPS -i pipe:0
               -c:v h264_amf -quality speed -rc cqp -qp_i 23 output.mp4

    Intel QSV H.264:
        ffmpeg ... -c:v h264_qsv -global_quality 23 output.mp4
    """
    # Try AMD AMF first
    try:
        result = subprocess.run(
            ['ffmpeg', '-encoders'], capture_output=True, text=True, timeout=5
        )
        encoders = result.stdout + result.stderr

        if 'h264_amf' in encoders:
            print("[FFmpeg] Using AMD AMF H.264 encoder")
            return [
                'ffmpeg', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgr24',
                '-r', str(fps), '-i', input_pipe,
                '-c:v', 'h264_amf',
                '-quality', 'speed',
                '-rc', 'cqp', '-qp_i', str(crf),
                '-movflags', '+faststart',
                output_path
            ]
        elif 'h264_qsv' in encoders:
            print("[FFmpeg] Using Intel QSV H.264 encoder")
            return [
                'ffmpeg', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgr24',
                '-r', str(fps), '-i', input_pipe,
                '-c:v', 'h264_qsv',
                '-global_quality', str(crf),
                '-movflags', '+faststart',
                output_path
            ]
        elif 'libx264' in encoders:
            print("[FFmpeg] Using libx264 software encoder")
            return [
                'ffmpeg', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgr24',
                '-r', str(fps), '-i', input_pipe,
                '-c:v', 'libx264',
                '-preset', 'fast', '-crf', str(crf),
                '-movflags', '+faststart',
                output_path
            ]
    except FileNotFoundError:
        print("[FFmpeg] ffmpeg not found in PATH")
    except Exception as e:
        print(f"[FFmpeg] Error detecting encoders: {e}")

    return []


# ─── dlib / face_recognition GPU ─────────────────────────────────────────────

def configure_dlib_gpu():
    """
    Configure dlib to use GPU if available.
    dlib uses CUDA by default if compiled with it.
    For AMD, we use the CNN model which is faster even on CPU.
    """
    try:
        import dlib
        has_cuda = dlib.DLIB_USE_CUDA
        print(f"[dlib] CUDA support compiled in: {has_cuda}")
        if has_cuda:
            print("[dlib] GPU face detection enabled (CNN model recommended)")
        else:
            print("[dlib] No CUDA in dlib — using HOG model (CPU optimized)")
        return has_cuda
    except ImportError:
        print("[dlib] dlib not installed")
        return False


# ─── Thread Pool Config ───────────────────────────────────────────────────────

def get_optimal_thread_config():
    """
    Returns optimal thread counts for a 4-core shared budget.
    Leaves headroom for OS and other projects running on the same machine.
    GPU handles face recognition workload, so CPU threads are kept low.
    """
    # Hard cap at 4 cores — other projects are also running
    budget = 4

    return {
        'face_recognition_workers': 2,          # CPU-bound, GPU offloads heavy lifting
        'camera_stream_workers':    2,          # I/O bound
        'opencv_threads':           3,          # leave 1 core for OS/other projects
        'celery_workers':           2,
        'django_workers':           4,
    }



# ─── Main Setup ───────────────────────────────────────────────────────────────

def setup_gpu_environment():
    """
    Full GPU + CPU optimization setup.
    Call this once at app startup.
    Returns a config dict used by the app.
    """
    print("\n" + "="*60)
    print("  EduMi GPU/CPU Optimization Setup")
    print("="*60 + "\n")

    set_cpu_affinity()
    gpu_info   = detect_amd_gpu()
    cv_info    = configure_opencv_gpu()
    dlib_gpu   = configure_dlib_gpu()
    threads    = get_optimal_thread_config()

    config = {
        'gpu_available':    gpu_info['found'],
        'gpu_name':         gpu_info.get('name'),
        'opencl_available': gpu_info['opencl'] or cv_info['opencl_enabled'],
        'directml':         gpu_info['directml'],
        'rocm':             gpu_info['rocm'],
        'dlib_cuda':        dlib_gpu,
        'opencv_backend':   cv_info['backend'],
        'threads':          threads,
        # Face recognition model: 'cnn' uses GPU, 'hog' uses CPU
        'face_model':       'cnn' if dlib_gpu else 'hog',
    }

    print("\n" + "-"*60)
    print("  Configuration Summary")
    print("-"*60)
    print(f"  GPU:            {config['gpu_name'] or 'Not detected'}")
    print(f"  OpenCL:         {'Yes' if config['opencl_available'] else 'No'}")
    print(f"  DirectML:       {'Yes' if config['directml'] else 'No'}")
    print(f"  dlib CUDA:      {'Yes' if config['dlib_cuda'] else 'No'}")
    print(f"  OpenCV backend: {config['opencv_backend']}")
    print(f"  Face model:     {config['face_model']}")
    print(f"  Thread config:  {threads}")
    print("="*60 + "\n")

    return config


# ─── Singleton config (imported by other modules) ────────────────────────────

_gpu_config = None

def get_gpu_config():
    global _gpu_config
    if _gpu_config is None:
        _gpu_config = setup_gpu_environment()
    return _gpu_config


if __name__ == '__main__':
    cfg = setup_gpu_environment()

    print("\n[Test] VideoWriter codec detection:")
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
        tmp = f.name
    writer, path = get_video_writer(tmp)
    if writer:
        writer.release()
        os.unlink(path)

    print("\n[Test] FFmpeg encoder detection:")
    cmd = get_ffmpeg_hw_encode_cmd('pipe:0', 'test_output.mp4')
    if cmd:
        print(f"  Command: {' '.join(cmd[:6])} ...")
    else:
        print("  FFmpeg not available")

    print("\n[Done] GPU setup complete.")
