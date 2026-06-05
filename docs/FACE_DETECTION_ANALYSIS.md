# 🧠 Face Detection & AI Attendance — Technical Analysis

> **Edumi2** | In-depth breakdown of the face recognition pipeline, attention tracking engine, attendance automation, and their real-world limitations.

---

## 📑 Table of Contents

1. [System Overview](#1-system-overview)
2. [Libraries & Tools Used](#2-libraries--tools-used)
3. [Phase 1 — Face Registration](#3-phase-1--face-registration)
4. [Phase 2 — Embedding Storage & Encryption](#4-phase-2--embedding-storage--encryption)
5. [Phase 3 — Live Attendance Verification (WebSocket)](#5-phase-3--live-attendance-verification-websocket)
6. [Phase 4 — Teacher-Side Face Tracking](#6-phase-4--teacher-side-face-tracking)
7. [Phase 5 — Emotion & Attention Estimation](#7-phase-5--emotion--attention-estimation)
8. [Phase 6 — Engagement Report Generation](#8-phase-6--engagement-report-generation)
9. [Anti-Spoofing Mechanisms](#9-anti-spoofing-mechanisms)
10. [Database Models](#10-database-models)
11. [Complete End-to-End Workflow](#11-complete-end-to-end-workflow)
12. [Configurable Parameters](#12-configurable-parameters)
13. [Known Limitations](#13-known-limitations)
14. [Future Improvements](#14-future-improvements)

---

## 1. System Overview

The face recognition and attendance system in Edumi2 is a **multi-phase, real-time pipeline** that spans:

- **Registration** — one-time face enrollment per student
- **Live Verification** — per-frame identity check during a live meeting (student side)
- **Live Tracking** — batch frame analysis from the teacher's dashboard (teacher side)
- **Emotion Estimation** — lightweight landmark-based attention scoring
- **Automated Reporting** — post-meeting engagement report generation via Celery

The system is designed with **privacy-first principles**: the original face photograph is never stored in an accessible form, and all biometric data is encrypted at rest using AES-256.

```
REGISTRATION FLOW                          LIVE SESSION FLOW
─────────────                              ─────────────────
Student → Browser Camera / Upload          Student Browser → WebSocket (frame)
    │                                           │
    ▼                                           ▼
FaceService.extract_embedding()         FaceService.compare_frame_to_stored()
    │                                           │
    ▼                                           ▼
AES-256 encrypt → DB (BinaryField)      Decrypt stored embedding → Compare
                                                │
                                                ▼
                                        Vote Buffer (2 consecutive matches)
                                                │
                                                ▼
                                        AttendanceRecord.status = "present"
```

---

## 2. Libraries & Tools Used

| Library | Version | Role | How It's Used |
|---|---|---|---|
| **`face_recognition`** | —  | Primary embedding engine | 128-d HOG-based face detection + "large" 68-landmark model encoding |
| **`OpenCV (cv2)`** | 4.13 | Fallback detection + image processing | Haar Cascade face detection, CLAHE low-light enhancement, Sobel edge features |
| **`Pillow (PIL)`** | 12.x | Image decoding | Converts raw bytes to RGB numpy arrays |
| **`NumPy`** | 2.4 | Numerical operations | Vector distance, array manipulation, brightness checks |
| **`cryptography` (Fernet)** | 42.x | AES-256 encryption | Encrypts/decrypts the 128-d float embedding at rest |
| **`Django Channels`** | 4.0 | WebSocket layer | Manages the real-time frame-push channel for both consumers |
| **`Celery`** | 5.3 | Background task queue | Offloads face registration processing from the request cycle |
| **`openpyxl`** | 3.1 | Excel export | Generates formatted `.xlsx` attendance reports |

### Primary vs. Fallback Detection

```
          ┌─────────────────────────────────────────────────┐
          │  face_recognition installed?                     │
          │                                                   │
          │   YES ──→ HOG detector + 68-point landmark model │
          │            → 128-d unit vector embedding          │
          │                                                   │
          │   NO  ──→ OpenCV Haar Cascade detector            │
          │            → 8×8 Grayscale + 8×8 Sobel Edge      │
          │            → Concatenated 128-d pseudo-vector     │
          └─────────────────────────────────────────────────┘
```

> **Note:** `face_recognition` is built on top of `dlib` and produces true metric-space 128-d vectors suitable for cosine/Euclidean distance comparison. The OpenCV fallback produces a structural pseudo-embedding that is less accurate but works when `dlib` cannot be installed (common on Windows without C++ build tools).

---

## 3. Phase 1 — Face Registration

**File:** [`attendance/views.py`](attendance/views.py) | [`attendance/tasks.py`](attendance/tasks.py)

Students register their face through one of two methods:

### Method A: File Upload (`/attendance/face/upload/`)
```
Student selects a photo file
    │
    ▼
views.upload_face_photo()
    ├── Read file bytes
    ├── FaceService.extract_embedding(image_bytes, live=False)
    │       ├── Low-light CLAHE enhancement (if avg brightness < 65)
    │       ├── face_recognition HOG detector
    │       ├── face_recognition 'large' model → 128-d embedding
    │       └── Quality score = (face_area / image_area) × 8, clamped 0–1
    │
    ├── FaceService.prepare_for_storage(embedding)
    │       ├── JSON encode the float list
    │       ├── SHA-256 checksum of the JSON string
    │       └── Fernet.encrypt(json_bytes) → ciphertext
    │
    └── StudentFaceProfile.update_or_create(
            face_embedding_encrypted = ciphertext,
            embedding_checksum       = sha256_hex,
            face_quality_score       = quality,
            face_photo               = photo_file,  ← admin-only
            registration_ip          = client_ip
        )
```

### Method B: Live Camera Capture (`/attendance/face/capture/`)
- The browser captures a `<canvas>` snapshot and sends it as a base64-encoded JPEG via AJAX POST.
- Identical processing pipeline to Method A.
- Real-time feedback is provided via `/attendance/face/detect/` — a lightweight endpoint that runs detection only (no embedding) to guide the student into position.

### Key Detail: `live=False` During Registration
Registration always runs with `live=False`, which **skips the liveness variance check**. This is intentional — an uploaded photo would fail the variance check since it has no inter-frame motion. The anti-spoofing is applied only during live sessions.

---

## 4. Phase 2 — Embedding Storage & Encryption

**File:** [`attendance/encryption_service.py`](attendance/encryption_service.py) | [`attendance/models.py`](attendance/models.py)

### Encryption: Fernet (AES-256-CBC + HMAC-SHA256)

```python
# Encrypt
json_bytes = json.dumps([0.123, -0.456, ...]).encode('utf-8')  # 128 floats
ciphertext = Fernet(FACE_ENCRYPTION_KEY).encrypt(json_bytes)
# → stored as BinaryField in DB

# Decrypt (at runtime)
decrypted = Fernet(key).decrypt(ciphertext)
embedding = json.loads(decrypted)  # back to list of 128 floats
```

### What is stored in `StudentFaceProfile`

| Field | Type | Content |
|---|---|---|
| `face_embedding_encrypted` | `BinaryField` | AES-256 Fernet ciphertext of the 128-d JSON vector |
| `embedding_checksum` | `CharField(64)` | SHA-256 hex digest of the plaintext JSON (integrity check) |
| `face_photo` | `ImageField` | Original photo — stored only for admin review, not used in matching |
| `face_quality_score` | `FloatField` | 0.0–1.0; derived from face-area-to-image-area ratio |
| `registration_ip` | `GenericIPAddressField` | Audit trail for the registration request |
| `is_active` | `BooleanField` | Can be toggled off without deleting the record |
| `last_verified_at` | `DateTimeField` | Updated every time a live match succeeds |

### Privacy Guarantee
- The 128-d float vector **cannot be used to reconstruct the original face photo** — it's a one-way mathematical signature.
- The photo file (`face_photo`) is only accessible to `is_superuser` users via `/attendance/admin/face-photos/`.
- The encryption key (`FACE_ENCRYPTION_KEY`) must be stored in `.env` and is **never logged**.

---

## 5. Phase 3 — Live Attendance Verification (WebSocket)

**File:** [`attendance/consumers.py`](attendance/consumers.py)

Route: `ws/attendance/<meeting_code>/`

This consumer runs on the **student's side** during a meeting. The browser periodically captures a webcam frame and sends it over the WebSocket.

### Connection Setup
```
Student browser connects → ws/attendance/<meeting_code>/
    │
    ├── Auth check (reject unauthenticated)
    ├── Superuser bypass (no FR needed for admins)
    ├── Load AttendanceSettings (threshold, interval, presence_duration)
    ├── Load encrypted embedding from StudentFaceProfile
    │
    └── Send: { type: "connected", interval: 15, has_profile: true }
```

### Per-Frame Processing Loop

```
Client sends: { type: "frame", frame: "<base64 JPEG>" }
    │
    ▼
base64.b64decode(frame_b64) → raw bytes
    │
    ▼
FaceService.compare_frame_to_stored(
    frame_bytes,
    encrypted_embedding,
    threshold      = 0.55,     # configurable per classroom
    prev_frame_bytes = last_frame  # for motion liveness
)
    │
    ├── [if prev_frame exists] Motion liveness check
    │       → resize both frames to 64×48 grayscale
    │       → mean(|frame_A - frame_B|) >= 1.5 required
    │       → FAIL → return "No motion detected — photo spoofing"
    │
    ├── extract_embedding(frame, live=True)
    │       → variance check: std_dev(grayscale) >= 6.0 required
    │       → HOG detection → 128-d encoding
    │
    ├── decrypt stored embedding
    │       → Fernet.decrypt → json.loads → numpy array
    │
    ├── face_recognition.face_distance([stored], live)
    │       → Euclidean distance in embedding space
    │       → confidence = 1.0 - distance
    │
    └── is_match = distance <= (1.0 - threshold)
                  = distance <= 0.45  (at default threshold=0.55)
```

### Rolling Vote Buffer (Anti-Flicker)

A single-frame match is NOT enough to log attendance. The system requires **2 consecutive matching frames** before counting a verified interval.

```
Frame 1: MATCH  → vote_buffer = [True]          (not full yet)
Frame 2: FAIL   → vote_buffer = []              (cleared on any failure)
Frame 3: MATCH  → vote_buffer = [True]
Frame 4: MATCH  → vote_buffer = [True, True]    ← FULL: verified!
                   verified_seconds += interval (e.g. +15s)
                   vote_buffer = []             (reset for next cycle)
```

### Marking Attendance

```
verified_seconds >= presence_duration (default: 30s)
    │
    ▼
AttendanceRecord.update_or_create(
    student = user,
    meeting = meeting,
    defaults = {
        status               = "present" or "late",
        face_match_confidence = confidence,
        face_verified_at      = now,
        verification_method   = "face_recognition"
    }
)

Late detection:
    minutes_since_start = (join_time - meeting.created_at).total_seconds() / 60
    status = "late" if minutes_since_start > late_threshold_minutes else "present"
```

### WebSocket Event Sequence (Student View)

| Event Type | Direction | Meaning |
|---|---|---|
| `connected` | Server → Client | Socket ready, sends capture interval |
| `no_profile` | Server → Client | Student has no face registered |
| `verification_progress` | Server → Client | Partial match, shows `X/30s verified` |
| `verification_failed` | Server → Client | Frame rejected (no face, mismatch, spoofing) |
| `attendance_marked` | Server → Client | Attendance confirmed — stops further captures |

---

## 6. Phase 4 — Teacher-Side Face Tracking

**File:** [`attendance/face_tracking_consumer.py`](attendance/face_tracking_consumer.py)

Route: `ws/face-tracking/<meeting_code>/`

This consumer runs on the **teacher's dashboard**. The teacher's browser captures video tiles from each student's LiveKit feed and sends them for batch recognition.

### Connection & Embedding Preload
```
Teacher connects → ws/face-tracking/<meeting_code>/
    │
    ├── Auth check: must be meeting host (teacher) or superuser
    │
    ├── _load_all_embeddings():
    │       → get all approved ClassroomMembership students
    │       → load all active StudentFaceProfile records
    │       → decrypt all embeddings into memory
    │       → store as list: [{user_id, name, vec}, ...]
    │
    └── Send: { type: "connected", count: N }
```

> All embeddings are pre-loaded into memory at connection time to avoid a DB round-trip per frame. This is critical for latency.

### Two Frame Submission Modes

**Mode 1: `frame`** — Single student frame
```json
{ "type": "frame", "student_id": 42, "frame": "<base64>" }
```

**Mode 2: `bulk_frame`** — All students in one message
```json
{
  "type": "bulk_frame",
  "frames": {
    "42": "<base64>",
    "87": "<base64>",
    "103": "<base64>"
  }
}
```

### Frame Processing (`_process_frame`)

```
raw bytes → PIL.Image → numpy RGB array
    │
    ├── Low-light CLAHE (if avg brightness < 65)
    │
    ├── face_recognition.face_locations(np_img, model='hog')
    │    [fallback: cv2.CascadeClassifier]
    │
    ├── face_recognition.face_encodings(np_img, locations, model='large')
    │    [fallback: Grayscale 8×8 + Sobel 8×8 concatenated]
    │
    ├── For each detected face:
    │   ├── Normalize bounding box to 0–1 ratios
    │   ├── np.argmin(face_distance(all_stored_vecs, enc))
    │   ├── if best_distance <= 0.45 → matched!
    │   └── _estimate_emotion(np_img, face_location)
    │
    └── Return overlay data: {
            face_visible, faces: [{box, name, user_id, confidence, emotion}],
            matched_user_id, matched_name, confidence
        }
```

### Snapshot Persistence (Every 4th Frame)

```python
SNAPSHOT_SAVE_INTERVAL = 4

if frame_count[student_id] % 4 == 0:
    StudentEngagementSnapshot.create(
        meeting, student, emotion, confidence, face_visible
    )
    # Also writes to CSV: media/meeting_logs/engagement_<code>.csv
```

---

## 7. Phase 5 — Emotion & Attention Estimation

**File:** [`attendance/face_tracking_consumer.py`](attendance/face_tracking_consumer.py) → `_estimate_emotion()`

Emotion is estimated **without any ML emotion model**. It uses only geometric heuristics derived from `face_recognition.face_landmarks()` — a 68-point facial keypoint map.

### Landmark Measurements Used

| Measurement | Landmarks Used | Formula |
|---|---|---|
| **Mouth openness** | `top_lip`, `bottom_lip` | `abs(mean_y(bottom_lip) - mean_y(top_lip))` |
| **Brow raise** | `left_eyebrow`, `left_eye` | `mean_y(eye) - mean_y(brow)` (positive = raised) |
| **Brow furrow** | `left_eyebrow`, `right_eyebrow` | `x(right_inner_brow) - x(left_inner_brow)` |
| **Eye asymmetry** | `left_eye`, `right_eye` | `abs(mean_y(left_eye) - mean_y(right_eye))` |
| **Eye Aspect Ratio (EAR)** | `left_eye`, `right_eye` | `(ver1 + ver2) / (2 × horizontal)` |

### Decision Tree

```
avg_EAR < 0.21
    → TIRED (eyes nearly closed / sleeping)

mouth_open > face_height × 0.25
    → SURPRISED (jaw dropped)

mouth_open > face_height × 0.12 AND brow_raise > face_height × 0.08
    → HAPPY (smile + raised brows)

brow_furrow < face_height × 0.15 AND brow_raise < face_height × 0.04
    → CONFUSED (brows close together, low)

eye_asymmetry > face_height × 0.06
    → DISTRACTED (eyes at different heights = looking sideways)

else
    → FOCUSED
```

### Emotion Weights for Engagement Scoring

```python
EMOTION_WEIGHTS = {
    'focused':    1.0,   # Full engagement
    'happy':      0.9,   # Positive, attentive
    'confused':   0.6,   # Present but struggling
    'distracted': 0.3,   # Partial attention
    'absent':     0.1,   # Not visible in frame
    'unknown':    0.1,   # Could not be determined
    # 'surprised' uses weight 0.1 (not listed, defaults to 0.1)
}
```

---

## 8. Phase 6 — Engagement Report Generation

**File:** [`attendance/engagement_service.py`](attendance/engagement_service.py)

Triggered when a teacher views a completed meeting's report (or via Celery on meeting end).

### Aggregation Logic

```
StudentEngagementSnapshot rows (all frames for this meeting)
    │
    ▼
Group by student_id
    │
    For each student:
    ├── dominant_emotion = most_common(emotions)
    ├── engagement_score = mean(EMOTION_WEIGHTS[e] for e in emotions) × 100
    └── presence_pct     = (visible_frames / total_frames) × 100
    │
    ▼
EngagementReport.update_or_create(
    meeting, classroom, teacher,
    student_data           = [per-student dicts],
    class_engagement_score = mean(all engagement_scores)
)
```

### Per-Student Output Structure

```json
{
  "user_id": 42,
  "name": "Tarun Kumar",
  "username": "tarunkumar",
  "dominant_emotion": "focused",
  "emotion_counts": { "focused": 18, "distracted": 3, "happy": 2 },
  "engagement_score": 92.5,
  "presence_pct": 95.6,
  "avg_confidence": 0.831,
  "total_snapshots": 23
}
```

### CSV Log
Every 4th recognized frame is also appended to `media/meeting_logs/engagement_<meeting_code>.csv`:

| Timestamp | User ID | Name | Expression | Status |
|---|---|---|---|---|
| 2026-06-05 10:15:30 | 42 | Tarun Kumar | Focused | Active |
| 2026-06-05 10:15:45 | 87 | Gaurav Singh | Distracted | Inactive/Distracted |

---

## 9. Anti-Spoofing Mechanisms

The system implements two lightweight spoofing countermeasures:

### 9.1 Motion Liveness Check (Inter-Frame)

Compares consecutive frames sent by the student's browser.

```
prev_frame → resize to 64×48 → grayscale float array
curr_frame → resize to 64×48 → grayscale float array
diff = mean(|curr - prev|)

if diff < 1.5:
    → BLOCKED: "No motion detected — possible photo spoofing"
```

**What it catches:** A static printed photo or a looped video held in front of the camera.  
**What it misses:** A person who is extremely still, or a high-quality video played on another device.

### 9.2 Liveness Variance Check (Per-Frame)

During live frames (`live=True`), the pixel standard deviation of the grayscale channel is checked.

```
gray_variance = std_dev(mean(R,G,B) for each pixel)

if gray_variance < 6.0:
    → BLOCKED: "Image appears to be a static photo or screen"
```

**What it catches:** Extremely flat, uniform images (blank screen, solid color card).  
**What it misses:** A high-resolution printed photo in varying light, or a phone screen with a video.

> **Honest Assessment:** These are heuristic checks, not cryptographic liveness. A determined attacker with a high-quality video replay can likely bypass both. Production deployments should consider a 3D depth sensor or active challenge-response liveness (blinking, head turning).

---

## 10. Database Models

**File:** [`attendance/models.py`](attendance/models.py)

```
StudentFaceProfile          (one per student)
├── student (OneToOne → User)
├── face_embedding_encrypted (BinaryField — AES-256)
├── embedding_checksum       (SHA-256 hex)
├── face_photo               (admin-only ImageField)
├── face_quality_score       (0.0–1.0)
├── is_active
└── last_verified_at

AttendanceRecord            (one per student per meeting)
├── student, meeting, classroom
├── date
├── status                  (present | absent | late | partial)
├── verification_method     (face_recognition | manual)
├── face_match_confidence   (0.0–1.0)
├── face_verified_at
├── marked_present_at
└── overridden_by + override_reason   ← teacher manual override

FaceRecognitionLog          (audit log — one row per frame attempt)
├── student, meeting
├── event_type              (match_success | match_failed | no_face | ...)
└── confidence_score

AttendanceSettings          (one per classroom — teacher configurable)
├── face_recognition_enabled
├── confidence_threshold     (default: 0.55)
├── presence_duration_seconds (default: 30)
├── late_threshold_minutes   (default: 10)
├── recognition_interval_seconds (default: 15)
└── enforce_schedule

StudentEngagementSnapshot   (one per recognized frame, every 4th)
├── meeting, student
├── emotion
├── confidence
└── face_visible

EngagementReport            (one per meeting, generated on end)
├── meeting, classroom, teacher
├── student_data            (JSONField — aggregated per-student stats)
└── class_engagement_score  (0–100)

FaceResetRequest            (student requests re-registration)
├── student, subject, reason
├── status                  (pending | approved | denied)
└── reviewed_by, admin_note

ClassSchedule               (teacher defines class days)
├── classroom, day_of_week
├── start_time, end_time
└── is_active
```

---

## 11. Complete End-to-End Workflow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 0 — PRE-CONDITION: FACE REGISTRATION                                     │
│                                                                                   │
│  Student → face_setup page                                                        │
│      ├── Upload photo OR capture from webcam                                     │
│      ├── FaceService.extract_embedding(bytes, live=False)                        │
│      │       ├── CLAHE if dark                                                   │
│      │       ├── HOG detect → 128-d encode (or Haar+Sobel fallback)             │
│      │       └── quality_score = face_area / image_area × 8                    │
│      ├── AES-256 encrypt → SHA-256 checksum                                     │
│      └── Save → StudentFaceProfile (DB)                                          │
└───────────────────────────────────────────┬─────────────────────────────────────┘
                                            │ (registration complete)
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1 — MEETING JOINS                                                         │
│                                                                                   │
│  Student joins meeting → KickedParticipant check → Face profile check           │
│      ├── No profile? → blocked from joining                                      │
│      └── Has profile? → LiveKit JWT token → WebRTC session starts               │
└───────────────────────────────────────────┬─────────────────────────────────────┘
                                            │
                                ┌───────────┴───────────┐
                                │                       │
                                ▼                       ▼
              ┌─────────────────────────┐  ┌──────────────────────────────────┐
              │  STUDENT WebSocket      │  │  TEACHER WebSocket               │
              │  ws/attendance/<code>/  │  │  ws/face-tracking/<code>/        │
              │                         │  │                                   │
              │  Every 15s:             │  │  Every frame (bulk_frame msg):   │
              │  capture webcam frame   │  │  for each student tile:          │
              │  → base64 → WS send     │  │  → detect faces in tile          │
              │                         │  │  → match against all embeddings  │
              │  Server:                │  │  → estimate emotion              │
              │  → liveness checks      │  │  → return overlay data           │
              │  → compare to stored    │  │  → save snapshot every 4th frame │
              │  → vote buffer (2 req.) │  │                                   │
              │  → accumulate seconds   │  │  Teacher sees: name box,         │
              │  → mark present@30s     │  │  emotion label, confidence %     │
              └─────────────────────────┘  └──────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 2 — MEETING ENDS                                                          │
│                                                                                   │
│  Teacher ends meeting → meeting.status = "ended"                                 │
│      │                                                                            │
│      ▼                                                                            │
│  generate_engagement_report(meeting_id)  [Celery / on-demand]                   │
│      ├── Aggregate all StudentEngagementSnapshot rows                            │
│      ├── Compute per-student: dominant_emotion, engagement_score, presence_pct  │
│      ├── Compute class_engagement_score (class mean)                             │
│      └── Save → EngagementReport (JSONField)                                     │
│                                                                                   │
│  Teacher Dashboard shows:                                                         │
│      ├── AttendanceRecord list (present/absent/late per student)                 │
│      ├── EngagementReport with per-student bar chart + emotion breakdown        │
│      ├── CSV download: media/meeting_logs/engagement_<code>.csv                  │
│      └── Excel export: /attendance/<classroom_id>/export/                        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Configurable Parameters

All parameters below are adjustable via **Teacher → Attendance Settings** (per classroom):

| Parameter | Default | Description | Code Location |
|---|---|---|---|
| `confidence_threshold` | `0.55` | Min similarity for a face match (0–1). Higher = stricter. | `AttendanceSettings`, `MATCH_THRESHOLD` in `face_service.py` |
| `presence_duration_seconds` | `30` | Total verified seconds needed to be marked Present | `AttendanceSettings` |
| `late_threshold_minutes` | `10` | Minutes after meeting start → student is "Late" not "Present" | `AttendanceSettings` |
| `recognition_interval_seconds` | `15` | How often (seconds) the browser sends a capture | `AttendanceSettings` |
| `face_recognition_enabled` | `True` | Toggle FR entirely for a classroom | `AttendanceSettings` |
| `enforce_schedule` | `False` | Only record attendance on scheduled class days | `AttendanceSettings` |
| `CONSECUTIVE_MATCHES_REQUIRED` | `2` | Frames that must match consecutively before counting | hardcoded in `consumers.py` |
| `SNAPSHOT_SAVE_INTERVAL` | `4` | Save 1 DB snapshot every N recognized frames | hardcoded in `face_tracking_consumer.py` |
| `MIN_LIVENESS_VARIANCE` | `6.0` | Minimum grayscale std-dev for live frame acceptance | `face_service.py` |
| `MIN_MOTION_DIFF` | `1.5` | Minimum inter-frame pixel diff for motion liveness | `face_service.py` |

---

## 13. Known Limitations

### 13.1 Accuracy Limitations

| Limitation | Impact | Severity |
|---|---|---|
| **`face_recognition` requires `dlib`** | On Windows without MSVC build tools, falls back to weaker OpenCV Haar+Sobel pseudo-embedding | HIGH |
| **HOG model used (not CNN)** | The `hog` detection model is faster but less accurate than `cnn` (GPU). Small or angled faces may not be detected. | MEDIUM |
| **Only 1 jitter during encoding** | `num_jitters=1` is fast but slightly less robust than `num_jitters=3`. Minor tradeoff. | LOW |
| **Static face registration** | Quality of registration photo determines all future match accuracy. Blur or poor lighting at registration hurts all future sessions. | HIGH |

### 13.2 Anti-Spoofing Limitations

| Attack Vector | Current Defense | Bypass Difficulty |
|---|---|---|
| **Printed photo** | Motion diff check | EASY (any movement nearby) |
| **Photo on phone screen** | Variance check (partially) | EASY (phone brightness varies) |
| **Video replay on another screen** | Motion diff (frames differ) | MEDIUM (looped video detected) |
| **High-quality face mask** | None | EASY |
| **Another person sitting in** | Face matching + teacher visual | HARD (teacher can see) |

### 13.3 Environmental Limitations

| Condition | Effect |
|---|---|
| **Low lighting** | CLAHE mitigates but does not fully compensate for extreme darkness |
| **Multiple faces in frame** | Only the face with highest confidence is matched per student tile |
| **Student looks away** | Emotion = "distracted", attendance timer paused (no match) |
| **Glasses / face mask** | Reduces landmark accuracy, may cause match failures |
| **High latency / bandwidth** | Frames arrive stale; confidence drops |
| **SQLite under heavy load** | The middleware retries locked DB; switch to PostgreSQL for >20 concurrent students |

### 13.4 Architecture Limitations

| Limitation | Details |
|---|---|
| **Embeddings in server RAM** | `FaceTrackingConsumer` loads all embeddings into memory per connection. For 100+ students this is acceptable (~100 × 128 × 8 bytes = ~100 KB), but grows linearly. |
| **No incremental learning** | Registration is a one-shot process. Re-registration requires a `FaceResetRequest` approved by admin. |
| **No multi-angle enrollment** | Only one embedding is stored per student. Enrolling multiple angles would improve robustness. |
| **Teacher controls tracking** | The teacher's browser must stay open for the tracking WebSocket to function. If teacher closes it, real-time tracking stops (attendance still works independently). |

---

## 14. Future Improvements

| Improvement | Benefit | Complexity |
|---|---|---|
| **Switch to CNN detection model** | Far better accuracy on small/partial faces at the cost of GPU requirement | MEDIUM |
| **Multi-angle enrollment (3–5 photos)** | Average embeddings across angles to improve match rate | LOW |
| **Active liveness challenge** | Ask student to blink, nod, or turn head — defeats photo/video replay | HIGH |
| **Dedicated ML emotion model** | Replace geometric heuristics with a model (e.g., FER2013 CNN or MediaPipe FaceBlendshapes) for more accurate emotion classification | HIGH |
| **Asynchronous face_registration via Celery** | Already scaffolded in `tasks.py` — just needs to be wired to the view | LOW |
| **Embedding versioning** | Store embedding model version so future algorithm upgrades can trigger re-enrollment | MEDIUM |
| **Face clustering / deduplication** | Detect if two accounts share the same face (prevent proxy attendance) | HIGH |
| **Encrypted transport for frames** | Frames sent over WSS (already enforced via Ngrok/HTTPS in production) | LOW |

---

## Summary

The Edumi2 face recognition system is a pragmatic, privacy-first implementation that:

✅ Uses **state-of-the-art 128-d face embeddings** (via `face_recognition` / `dlib`) with a graceful OpenCV fallback  
✅ Stores **no raw biometric images** accessible at runtime — only AES-256 encrypted vectors  
✅ Implements **two layers of anti-spoofing** (motion diff + variance check)  
✅ Uses a **rolling vote buffer** to prevent flicker-based false attendance  
✅ Generates **per-student engagement reports** from lightweight landmark geometry  
✅ Is **fully configurable per classroom** by the teacher without code changes  

⚠️ Its primary weaknesses are the **heuristic-only anti-spoofing** and the **dependency on `dlib`** installation for full accuracy, both of which are addressable with the improvements listed above.

---

*Analysis by [Tarun Kumar](https://github.com/tarunkumar-sys) & [Gaurav Singh](https://github.com/GAuravgiy87)*
