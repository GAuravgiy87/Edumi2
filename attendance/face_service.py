"""
Face recognition service.

Uses the `face_recognition` library (dlib) to:
  1. Extract a 128-d numerical embedding from an image.
  2. Compare a live video frame against a stored embedding.

NO IMAGES ARE EVER WRITTEN TO DISK.
All processing happens in memory.
"""
import io
import hashlib
import json
import logging
from typing import Optional

import numpy as np

from .encryption_service import FaceEncryptionService

logger = logging.getLogger('attendance.face_service')

# Euclidean distance threshold: lower = stricter match
# face_recognition default is 0.6; we use 0.5 for higher accuracy
MATCH_THRESHOLD = 0.50
MIN_QUALITY_SCORE = 0.15   # reject frames where face is too small


class FaceService:
    """
    All face processing lives here.
    Instances are cheap; create one per request/consumer.
    """

    def __init__(self):
        self._encryptor = FaceEncryptionService()

    # ─────────────────────────────────────────────────────
    #  PUBLIC: extract embedding from raw image bytes
    # ─────────────────────────────────────────────────────
    def extract_embedding(self, image_bytes: bytes) -> dict:
        """
        Extract a 128-d face embedding from image bytes.

        Returns a dict:
            {
                'status': 'success' | 'no_face' | 'multiple_faces' | 'low_quality' | 'error',
                'embedding': list[float] | None,
                'quality': float,   # 0–1
                'message': str,
            }
        """
        try:
            import face_recognition
            from PIL import Image

            pil_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            np_img = np.array(pil_img)

            face_locations = face_recognition.face_locations(np_img, model='hog')

            if not face_locations:
                return _result('no_face', None, 0.0, 'No face detected in image.')

            if len(face_locations) > 1:
                return _result('multiple_faces', None, 0.0,
                               f'{len(face_locations)} faces detected; only one allowed.')

            # Quality: face bounding-box area / image area
            top, right, bottom, left = face_locations[0]
            face_area = (bottom - top) * (right - left)
            img_area  = np_img.shape[0] * np_img.shape[1]
            quality   = min(1.0, round((face_area / img_area) * 8, 3))

            if quality < MIN_QUALITY_SCORE:
                return _result('low_quality', None, quality,
                               'Face too small or blurry; please move closer to the camera.')

            encodings = face_recognition.face_encodings(np_img, face_locations)
            if not encodings:
                return _result('no_face', None, 0.0, 'Could not encode face landmarks.')

            return _result('success', encodings[0].tolist(), quality, 'OK')

        except ImportError:
            logger.error("face_recognition library not installed.")
            return _result('error', None, 0.0,
                           'face_recognition library is not installed on the server.')
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
    ) -> dict:
        """
        Compare a live camera frame (JPEG bytes) to the student's stored embedding.

        Returns:
            {
                'match': bool,
                'confidence': float,   # 0–1 (higher = more similar)
                'distance': float,     # raw L2 distance
                'event': str,          # FaceRecognitionLog.EVENT_CHOICES key
                'message': str,
            }
        """
        live = self.extract_embedding(frame_bytes)

        if live['status'] != 'success':
            return {
                'match': False,
                'confidence': 0.0,
                'distance': 1.0,
                'event': live['status'],
                'message': live['message'],
            }

        try:
            import face_recognition
            stored_list = self._encryptor.decrypt_embedding(encrypted_embedding)
            stored_vec  = np.array(stored_list)
            live_vec    = np.array(live['embedding'])

            distance   = float(face_recognition.face_distance([stored_vec], live_vec)[0])
            confidence = round(max(0.0, 1.0 - distance), 4)
            is_match   = distance <= MATCH_THRESHOLD

            return {
                'match':      is_match,
                'confidence': confidence,
                'distance':   round(distance, 4),
                'event':      'match_success' if is_match else 'match_failed',
                'message':    'Face verified.' if is_match else 'Face did not match.',
            }
        except Exception as exc:
            logger.exception(f"Comparison failed: {exc}")
            return {
                'match': False, 'confidence': 0.0, 'distance': 1.0,
                'event': 'error', 'message': str(exc),
            }

    # ─────────────────────────────────────────────────────
    #  PUBLIC: encrypt + checksum ready for DB storage
    # ─────────────────────────────────────────────────────
    def prepare_for_storage(self, embedding_list: list) -> tuple:
        """
        Returns (encrypted_bytes, sha256_checksum_hex).
        Store both in StudentFaceProfile.
        """
        json_str  = json.dumps(embedding_list)
        checksum  = hashlib.sha256(json_str.encode()).hexdigest()
        encrypted = self._encryptor.encrypt_embedding(embedding_list)
        return encrypted, checksum


# ─────────────────────────────────────────────────────────────
#  Helper
# ─────────────────────────────────────────────────────────────
def _result(status, embedding, quality, message):
    return {
        'status':    status,
        'embedding': embedding,
        'quality':   quality,
        'message':   message,
    }
