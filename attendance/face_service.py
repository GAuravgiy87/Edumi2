"""
Face recognition service — high-accuracy, anti-spoofing, low-light enhanced.

  - Uses 'large' face landmark model (68 points) for better encoding accuracy
  - Anti-spoofing motion liveness: only applied during live WebSocket frames,
    NOT during registration (which is intentionally a static photo/upload)
  - Strict distance threshold with per-classroom override
  - Low-light enhancement with CLAHE and gamma correction
  - Multi-scale detection for varying lighting conditions
"""
import io
import hashlib
import json
import logging
from typing import Optional, Tuple

from .encryption_service import FaceEncryptionService

logger = logging.getLogger('attendance.face_service')

MATCH_THRESHOLD   = 0.55   # default; overridden per-classroom
MIN_QUALITY_SCORE = 0.08
# Minimum pixel std-dev — only used for live frames, not registration uploads
MIN_LIVENESS_VARIANCE = 6.0
# Minimum motion diff between two consecutive live frames
MIN_MOTION_DIFF = 1.5

# Low-light enhancement parameters
LOW_LIGHT_THRESHOLD = 60  # Average brightness below this triggers enhancement
CLAHE_CLIP_LIMIT = 2.0
CLAHE_GRID_SIZE = (8, 8)
GAMMA_CORRECTION = 0.6  # < 1.0 brightens dark images


class FaceService:

    def __init__(self):
        self._encryptor = FaceEncryptionService()

    # ─────────────────────────────────────────────────────
    #  PRIVATE: Low-light image enhancement
    # ─────────────────────────────────────────────────────
    def _enhance_low_light(self, np_img: 'np.ndarray') -> 'np.ndarray':
        """
        Enhance image for low-light conditions using CLAHE and gamma correction.
        Returns enhanced image if low light detected, otherwise original.
        """
        import numpy as np
        
        # Convert to LAB color space for better processing
        if len(np_img.shape) == 3:
            import cv2
            lab = cv2.cvtColor(np_img, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            
            # Check average brightness
            avg_brightness = np.mean(l)
            
            if avg_brightness < LOW_LIGHT_THRESHOLD:
                logger.debug(f"Low light detected (brightness={avg_brightness:.1f}), applying enhancement")
                
                # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
                clahe = cv2.createCLAHE(
                    clipLimit=CLAHE_CLIP_LIMIT,
                    tileGridSize=CLAHE_GRID_SIZE
                )
                l_enhanced = clahe.apply(l)
                
                # Apply gamma correction
                l_enhanced = self._apply_gamma_correction(l_enhanced, GAMMA_CORRECTION)
                
                # Merge channels back
                lab_enhanced = cv2.merge([l_enhanced, a, b])
                enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
                
                return enhanced
            
            return np_img
        else:
            # Grayscale image
            avg_brightness = np.mean(np_img)
            if avg_brightness < LOW_LIGHT_THRESHOLD:
                import cv2
                clahe = cv2.createCLAHE(
                    clipLimit=CLAHE_CLIP_LIMIT,
                    tileGridSize=CLAHE_GRID_SIZE
                )
                enhanced = clahe.apply(np_img)
                enhanced = self._apply_gamma_correction(enhanced, GAMMA_CORRECTION)
                return enhanced
            return np_img

    def _apply_gamma_correction(self, image: 'np.ndarray', gamma: float) -> 'np.ndarray':
        """Apply gamma correction to brighten/darken image."""
        import numpy as np
        # Build lookup table
        inv_gamma = 1.0 / gamma
        table = np.array([
            ((i / 255.0) ** inv_gamma) * 255
            for i in np.arange(0, 256)
        ]).astype("uint8")
        
        import cv2
        return cv2.LUT(image, table)

    def _detect_face_multiscale(self, np_img: 'np.ndarray', model: str = 'hog') -> list:
        """
        Try face detection at multiple scales and with/without enhancement.
        Returns list of face locations.
        """
        import face_recognition
        import numpy as np
        import cv2
        
        face_locations = []
        
        # Try 1: Original image
        face_locations = face_recognition.face_locations(np_img, model=model)
        if face_locations:
            return face_locations
        
        # Try 2: Low-light enhanced version
        enhanced_img = self._enhance_low_light(np_img)
        if not np.array_equal(enhanced_img, np_img):
            face_locations = face_recognition.face_locations(enhanced_img, model=model)
            if face_locations:
                logger.debug("Face detected after low-light enhancement")
                return face_locations
        
        # Try 3: Upscale small images (helps with distant faces in low light)
        h, w = np_img.shape[:2]
        if h < 480 or w < 640:
            scale = 2
            upscaled = cv2.resize(np_img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
            face_locations = face_recognition.face_locations(upscaled, model=model)
            if face_locations:
                # Scale back coordinates
                face_locations = [
                    (top // scale, right // scale, bottom // scale, left // scale)
                    for top, right, bottom, left in face_locations
                ]
                logger.debug("Face detected after upscaling")
                return face_locations
        
        # Try 4: Combined enhancement + upscaling for very challenging conditions
        if not np.array_equal(enhanced_img, np_img):
            h, w = enhanced_img.shape[:2]
            if h < 480 or w < 640:
                scale = 2
                upscaled = cv2.resize(enhanced_img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
                face_locations = face_recognition.face_locations(upscaled, model=model)
                if face_locations:
                    face_locations = [
                        (top // scale, right // scale, bottom // scale, left // scale)
                        for top, right, bottom, left in face_locations
                    ]
                    logger.debug("Face detected after enhancement + upscaling")
                    return face_locations
        
        return face_locations

    def _estimate_lighting_quality(self, np_img: 'np.ndarray') -> dict:
        """
        Estimate lighting quality metrics for the image.
        Returns dict with brightness, contrast, and quality score.
        """
        import numpy as np
        import cv2
        
        if len(np_img.shape) == 3:
            gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
        else:
            gray = np_img
        
        brightness = np.mean(gray)
        contrast = np.std(gray)
        
        # Calculate histogram spread
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist_spread = np.sum(hist > 0) / 256.0
        
        # Quality score (0-1)
        brightness_score = min(1.0, brightness / 128.0)
        contrast_score = min(1.0, contrast / 64.0)
        quality = (brightness_score + contrast_score + hist_spread) / 3.0
        
        return {
            'brightness': float(brightness),
            'contrast': float(contrast),
            'hist_spread': float(hist_spread),
            'quality_score': round(quality, 3),
            'is_low_light': brightness < LOW_LIGHT_THRESHOLD
        }

    # ─────────────────────────────────────────────────────
    #  PUBLIC: extract embedding from raw image bytes
    #  live=False  → registration (skip liveness variance check)
    #  live=True   → live frame (apply liveness variance check)
    # ─────────────────────────────────────────────────────
    def extract_embedding(self, image_bytes: bytes, live: bool = False, enhance_low_light: bool = True) -> dict:
        """
        Extract a 128-d face embedding with low-light enhancement.
        Returns: {status, embedding, quality, message, lighting_info}
        """
        try:
            import face_recognition
            import numpy as np
            from PIL import Image

            pil_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            np_img  = np.array(pil_img)

            # ── Estimate lighting conditions ──
            lighting_info = self._estimate_lighting_quality(np_img)
            logger.debug(f"Lighting info: {lighting_info}")

            # ── Liveness variance check (live frames only) ──
            # Printed photos / screen-grabs have very low pixel variance.
            # Skip this for registration uploads — they are intentionally static.
            if live:
                gray_var = float(np.std(np.mean(np_img, axis=2)))
                if gray_var < MIN_LIVENESS_VARIANCE:
                    return _result('low_quality', None, 0.0,
                                   'Image appears to be a static photo or screen. '
                                   'Please use a live camera feed.', lighting_info)

            # ── Face detection with multi-scale and low-light enhancement ──
            if enhance_low_light:
                face_locations = self._detect_face_multiscale(np_img, model='hog')
            else:
                face_locations = face_recognition.face_locations(np_img, model='hog')

            if not face_locations:
                # Provide helpful message based on lighting
                if lighting_info['is_low_light']:
                    return _result('no_face', None, 0.0, 
                                   'No face detected. Low light detected — please move to a brighter area '
                                   'or ensure your face is well-lit.', lighting_info)
                return _result('no_face', None, 0.0, 'No face detected.', lighting_info)

            if len(face_locations) > 1:
                return _result('multiple_faces', None, 0.0,
                               f'{len(face_locations)} faces detected; only one allowed.', lighting_info)

            # ── Quality: face area ratio ──────────────────
            top, right, bottom, left = face_locations[0]
            face_area = (bottom - top) * (right - left)
            img_area  = np_img.shape[0] * np_img.shape[1]
            quality   = min(1.0, round((face_area / img_area) * 8, 3))

            # Adjust quality score based on lighting
            quality = quality * (0.5 + 0.5 * lighting_info['quality_score'])

            if quality < MIN_QUALITY_SCORE:
                msg = 'Face too small — move closer to the camera.'
                if lighting_info['is_low_light']:
                    msg += ' Also, low light detected — please improve lighting.'
                return _result('low_quality', None, quality, msg, lighting_info)

            # ── Encode with 'large' model (68 landmarks, more accurate) ──
            # Use enhanced image for encoding if low light
            if enhance_low_light and lighting_info['is_low_light']:
                np_img = self._enhance_low_light(np_img)
            
            encodings = face_recognition.face_encodings(
                np_img, face_locations, num_jitters=2, model='large'
            )
            if not encodings:
                return _result('no_face', None, 0.0, 'Could not encode face landmarks.', lighting_info)

            return _result('success', encodings[0].tolist(), quality, 'OK', lighting_info)

        except ImportError:
            logger.error("face_recognition library not installed.")
            return _result('error', None, 0.0, 'face_recognition not installed on server.', {})
        except Exception as exc:
            logger.exception(f"Embedding extraction failed: {exc}")
            return _result('error', None, 0.0, str(exc), {})

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
def _result(status, embedding, quality, message, lighting_info=None):
    result = {'status': status, 'embedding': embedding, 'quality': quality, 'message': message}
    if lighting_info:
        result['lighting_info'] = lighting_info
    return result
