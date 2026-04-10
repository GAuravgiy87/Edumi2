"""
Face recognition service — high-accuracy, anti-spoofing, GPU-accelerated.

  - Uses 'large' face landmark model (68 points) for better encoding accuracy
  - Anti-spoofing motion liveness: only applied during live WebSocket frames,
    NOT during registration (which is intentionally a static photo/upload)
  - Strict distance threshold with per-classroom override
  - OpenCL/GPU acceleration via OpenCV when AMD GPU is available
  - CNN face detection model when dlib CUDA is available
"""
import io
import hashlib
import json
import logging
from typing import Optional
import concurrent.futures

from .encryption_service import FaceEncryptionService

logger = logging.getLogger('attendance.face_service')

MATCH_THRESHOLD   = 0.55   # default; overridden per-classroom
MIN_QUALITY_SCORE = 0.08
# Minimum pixel std-dev — only used for live frames, not registration uploads
MIN_LIVENESS_VARIANCE = 6.0
# Minimum motion diff between two consecutive live frames
MIN_MOTION_DIFF = 1.5

# ── GPU config (loaded once) ──────────────────────────────────────────────────
def _load_gpu_config():
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from scripts.gpu_setup import get_gpu_config
        return get_gpu_config()
    except Exception:
        return {'face_model': 'hog', 'opencl_available': False, 'threads': {'face_recognition_workers': 4}}

_GPU_CONFIG = None

def _get_gpu_config():
    global _GPU_CONFIG
    if _GPU_CONFIG is None:
        _GPU_CONFIG = _load_gpu_config()
    return _GPU_CONFIG


class FaceService:

    def __init__(self):
        self._encryptor = FaceEncryptionService()

    # ─────────────────────────────────────────────────────
    #  PUBLIC: extract embedding from raw image bytes
    #  live=False  → registration (skip liveness variance check)
    #  live=True   → live frame (apply liveness variance check)
    # ─────────────────────────────────────────────────────
    def extract_embedding(self, image_bytes: bytes, live: bool = False) -> dict:
        """
        Extract a 128-d face embedding.
        Returns: {status, embedding, quality, message}
        Uses CNN model when GPU/dlib-CUDA is available, HOG otherwise.
        """
        try:
            import face_recognition
            import numpy as np
            from PIL import Image

            cfg = _get_gpu_config()
            face_model = cfg.get('face_model', 'hog')

            pil_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            np_img  = np.array(pil_img)

            # ── Low-light enhancement (GPU-accelerated via OpenCL) ────────
            np_img = self._enhance_low_light(np_img)

            # ── Liveness variance check (live frames only) ──
            if live:
                gray_var = float(np.std(np.mean(np_img, axis=2)))
                if gray_var < MIN_LIVENESS_VARIANCE:
                    return _result('low_quality', None, 0.0,
                                   'Image appears to be a static photo or screen. '
                                   'Please use a live camera feed.')

            # ── Face detection: CNN (GPU) or HOG (CPU) ────────────────────
            face_locations = face_recognition.face_locations(np_img, model=face_model)

            if not face_locations:
                return _result('no_face', None, 0.0, 'No face detected.')

            if len(face_locations) > 1:
                return _result('multiple_faces', None, 0.0,
                               f'{len(face_locations)} faces detected; only one allowed.')

            # ── Quality: face area ratio ──────────────────
            top, right, bottom, left = face_locations[0]
            face_area = (bottom - top) * (right - left)
            img_area  = np_img.shape[0] * np_img.shape[1]
            quality   = min(1.0, round((face_area / img_area) * 8, 3))

            if quality < MIN_QUALITY_SCORE:
                return _result('low_quality', None, quality,
                               'Face too small — move closer to the camera.')

            # ── Encode with 'large' model (68 landmarks, more accurate) ──
            # num_jitters=1 on GPU (fast enough), 2 on CPU
            jitters = 1 if face_model == 'cnn' else 2
            encodings = face_recognition.face_encodings(
                np_img, face_locations, num_jitters=jitters, model='large'
            )
            if not encodings:
                return _result('no_face', None, 0.0, 'Could not encode face landmarks.')

            return _result('success', encodings[0].tolist(), quality, 'OK')

        except ImportError:
            logger.error("face_recognition library not installed.")
            return _result('error', None, 0.0, 'face_recognition not installed on server.')
        except Exception as exc:
            logger.exception(f"Embedding extraction failed: {exc}")
            return _result('error', None, 0.0, str(exc))

    # ─────────────────────────────────────────────────────
    #  PUBLIC: compare live frame against stored embedding
    # ─────────────────────────────────────────────────────
    def compare_frame_to_stored(
        self,
        frame_bytes: bytes,
        encrypted_embedding: bytes,
        threshold: float = MATCH_THRESHOLD,
        prev_frame_bytes: Optional[bytes] = None,
    ) -> dict:
        """
        Compare a live camera frame to the student's stored embedding.

        Args:
            frame_bytes:          Current JPEG frame
            encrypted_embedding:  Stored encrypted embedding
            threshold:            Match threshold (0–1); higher = stricter
            prev_frame_bytes:     Previous frame for motion liveness check

        Returns: {match, confidence, distance, event, message, liveness_ok}
        """
        # ── Motion liveness check (only when we have a previous frame) ──
        if prev_frame_bytes is not None:
            liveness_ok = self._check_motion_liveness(frame_bytes, prev_frame_bytes)
            if not liveness_ok:
                return {
                    'match': False, 'confidence': 0.0, 'distance': 1.0,
                    'event': 'low_quality', 'liveness_ok': False,
                    'message': 'No motion detected — possible photo spoofing attempt.',
                }

        # live=True: apply variance check on live frames
        live_result = self.extract_embedding(frame_bytes, live=True)

        if live_result['status'] != 'success':
            return {
                'match': False, 'confidence': 0.0, 'distance': 1.0,
                'event': live_result['status'], 'liveness_ok': True,
                'message': live_result['message'],
            }

        try:
            import face_recognition
            import numpy as np

            stored_list = self._encryptor.decrypt_embedding(encrypted_embedding)
            stored_vec  = np.array(stored_list)
            live_vec    = np.array(live_result['embedding'])

            distance   = float(face_recognition.face_distance([stored_vec], live_vec)[0])
            confidence = round(max(0.0, 1.0 - distance), 4)
            # threshold=0.55 → distance must be <= 0.45 to match
            is_match   = distance <= (1.0 - threshold)

            return {
                'match':       is_match,
                'confidence':  confidence,
                'distance':    round(distance, 4),
                'event':       'match_success' if is_match else 'match_failed',
                'liveness_ok': True,
                'message':     'Face verified.' if is_match else f'Face did not match (dist={distance:.3f}).',
            }
        except Exception as exc:
            logger.exception(f"Comparison failed: {exc}")
            return {
                'match': False, 'confidence': 0.0, 'distance': 1.0,
                'event': 'error', 'liveness_ok': True, 'message': str(exc),
            }

    # ─────────────────────────────────────────────────────
    #  PUBLIC: encrypt + checksum ready for DB storage
    # ─────────────────────────────────────────────────────
    def prepare_for_storage(self, embedding_list: list) -> tuple:
        json_str  = json.dumps(embedding_list)
        checksum  = hashlib.sha256(json_str.encode()).hexdigest()
        encrypted = self._encryptor.encrypt_embedding(embedding_list)
        return encrypted, checksum

    # ─────────────────────────────────────────────────────
    #  PRIVATE: motion-based liveness
    # ─────────────────────────────────────────────────────
    def _check_motion_liveness(self, frame_bytes: bytes, prev_frame_bytes: bytes) -> bool:
        """
        Returns True if there is enough pixel motion between two frames.
        A printed photo held in front of the camera will have near-zero motion.
        Threshold is intentionally loose to avoid false rejections from slight
        camera shake or compression artifacts.
        """
        try:
            import numpy as np
            from PIL import Image

            def to_gray_small(b):
                img = Image.open(io.BytesIO(b)).convert('L').resize((64, 48))
                return np.array(img, dtype=np.float32)

            a = to_gray_small(frame_bytes)
            b = to_gray_small(prev_frame_bytes)
            diff = float(np.mean(np.abs(a - b)))
            return diff >= MIN_MOTION_DIFF
        except Exception:
            return True  # if check fails, don't block

    def _enhance_low_light(self, np_img):
        """
        Applies CLAHE via OpenCV with OpenCL (GPU) acceleration when available.
        Falls back to CPU if OpenCL is not available.
        """
        try:
            import cv2
            import numpy as np

            avg_brightness = np.mean(np_img)
            if avg_brightness > 65:
                return np_img

            # Use OpenCL UMat for GPU-accelerated processing if available
            use_opencl = cv2.ocl.useOpenCL()

            if use_opencl:
                # Upload to GPU memory
                lab = cv2.cvtColor(cv2.UMat(np_img), cv2.COLOR_RGB2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                cl = clahe.apply(l)
                limg = cv2.merge((cl, a, b))
                enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2RGB)
                return enhanced.get()  # Download from GPU
            else:
                lab = cv2.cvtColor(np_img, cv2.COLOR_RGB2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                cl = clahe.apply(l)
                limg = cv2.merge((cl, a, b))
                return cv2.cvtColor(limg, cv2.COLOR_LAB2RGB)
        except Exception as e:
            logger.warning(f"Low-light enhancement failed: {e}")
            return np_img


# ─────────────────────────────────────────────────────────────
#  Module-level singleton — avoids re-instantiating Fernet on every frame
# ─────────────────────────────────────────────────────────────
_service_instance: Optional[FaceService] = None


def get_face_service() -> FaceService:
    global _service_instance
    if _service_instance is None:
        _service_instance = FaceService()
    return _service_instance


# ─────────────────────────────────────────────────────────────
#  Helper
# ─────────────────────────────────────────────────────────────
def _result(status, embedding, quality, message):
    return {'status': status, 'embedding': embedding, 'quality': quality, 'message': message}
