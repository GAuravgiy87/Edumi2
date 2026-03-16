from django.db import models
from django.contrib.auth.models import User


# ─────────────────────────────────────────────────────────────
#  1.  STUDENT FACE PROFILE
#      Stores AES-256 encrypted face embeddings.
#      The original photo is NEVER written to disk.
# ─────────────────────────────────────────────────────────────
class StudentFaceProfile(models.Model):
    """
    Secure storage for a student's face embedding (128-d float vector).
    Only the encrypted numerical representation is persisted – no images.
    """
    student = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='face_profile'
    )
    # AES-256 (Fernet) encrypted JSON of the float array
    face_embedding_encrypted = models.BinaryField()
    # SHA-256 hash for integrity verification on decryption
    embedding_checksum = models.CharField(max_length=64)

    is_active = models.BooleanField(default=True)
    face_quality_score = models.FloatField(default=0.0)   # 0.0–1.0
    registration_ip = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Student Face Profile'
        verbose_name_plural = 'Student Face Profiles'
        permissions = [
            ('view_face_embedding', 'Can view face embedding (recognition service only)'),
        ]

    def __str__(self):
        return f"FaceProfile({self.student.username})"


# ─────────────────────────────────────────────────────────────
#  2.  CLASS SCHEDULE
#      Teacher defines which days of the week classes run.
# ─────────────────────────────────────────────────────────────
class ClassSchedule(models.Model):
    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]

    classroom = models.ForeignKey(
        'meetings.Classroom', on_delete=models.CASCADE,
        related_name='schedules'
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_schedules'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['classroom', 'day_of_week']
        ordering = ['day_of_week', 'start_time']
        verbose_name = 'Class Schedule'
        verbose_name_plural = 'Class Schedules'

    def __str__(self):
        return f"{self.classroom.title} — {self.get_day_of_week_display()}"


# ─────────────────────────────────────────────────────────────
#  3.  ATTENDANCE RECORD
#      One row per student per meeting. Auto-created by FR pipeline.
# ─────────────────────────────────────────────────────────────
class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent',  'Absent'),
        ('late',    'Late'),
        ('partial', 'Partial'),
    ]
    VERIFICATION_METHOD = [
        ('face_recognition', 'Face Recognition'),
        ('manual',           'Manual Override'),
    ]

    student = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    meeting = models.ForeignKey(
        'meetings.Meeting', on_delete=models.CASCADE,
        related_name='face_attendance_records'
    )
    classroom = models.ForeignKey(
        'meetings.Classroom', on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='absent')
    verification_method = models.CharField(
        max_length=20, choices=VERIFICATION_METHOD,
        default='face_recognition'
    )
    face_match_confidence = models.FloatField(default=0.0)
    face_verified_at = models.DateTimeField(null=True, blank=True)
    marked_present_at = models.DateTimeField(null=True, blank=True)

    # Teacher override
    overridden_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='overridden_attendance'
    )
    override_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'meeting']
        ordering = ['-date', 'student']
        indexes = [
            models.Index(fields=['date', 'classroom']),
            models.Index(fields=['student', 'date']),
        ]

    def __str__(self):
        return (f"{self.student.username} | "
                f"{self.meeting.title} | {self.date} | {self.status}")

    def get_confidence_pct(self):
        return f"{self.face_match_confidence * 100:.1f}%"


# ─────────────────────────────────────────────────────────────
#  4.  FACE RECOGNITION LOG
#      Audit trail for every recognition attempt.
#      NO images are ever stored.
# ─────────────────────────────────────────────────────────────
class FaceRecognitionLog(models.Model):
    EVENT_CHOICES = [
        ('match_success',   'Match Success'),
        ('match_failed',    'Match Failed'),
        ('no_face',         'No Face Detected'),
        ('multiple_faces',  'Multiple Faces Detected'),
        ('low_quality',     'Low Image Quality'),
        ('no_profile',      'No Face Profile Registered'),
        ('error',           'Processing Error'),
    ]

    student = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='recognition_logs'
    )
    meeting = models.ForeignKey(
        'meetings.Meeting', on_delete=models.CASCADE,
        related_name='recognition_logs'
    )
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    confidence_score = models.FloatField(default=0.0)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['student', 'meeting']),
        ]

    def __str__(self):
        return f"{self.student.username} | {self.event_type} | {self.timestamp}"


# ─────────────────────────────────────────────────────────────
#  5.  ATTENDANCE SETTINGS
#      Per-classroom configuration controlled by the teacher.
# ─────────────────────────────────────────────────────────────
class AttendanceSettings(models.Model):
    classroom = models.OneToOneField(
        'meetings.Classroom', on_delete=models.CASCADE,
        related_name='attendance_settings'
    )
    face_recognition_enabled = models.BooleanField(default=True)
    # Minimum cosine-similarity confidence (0–1) to count as a match
    confidence_threshold = models.FloatField(default=0.55)
    # Cumulative verified seconds needed to be marked Present
    presence_duration_seconds = models.IntegerField(default=30)
    # Minutes after session start past which student is marked Late
    late_threshold_minutes = models.IntegerField(default=10)
    # How often (seconds) the client sends a frame for recognition
    recognition_interval_seconds = models.IntegerField(default=15)
    # Only record attendance on scheduled class days
    enforce_schedule = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Attendance Settings'
        verbose_name_plural = 'Attendance Settings'

    def __str__(self):
        return f"Settings for {self.classroom.title}"
