from django.db import models
from django.contrib.auth.models import User

class Camera(models.Model):
    name = models.CharField(max_length=100)
    rtsp_url = models.CharField(max_length=500)
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)
    ip_address = models.CharField(max_length=50)
    port = models.IntegerField(default=554)
    stream_path = models.CharField(max_length=200, default='/stream')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    def get_full_rtsp_url(self):
        from urllib.parse import quote
        if self.username and self.password:
            # Quote username and password to handle special chars like '@'
            safe_user = quote(self.username)
            safe_pass = quote(self.password)
            return f"rtsp://{safe_user}:{safe_pass}@{self.ip_address}:{self.port}{self.stream_path}"
        return f"rtsp://{self.ip_address}:{self.port}{self.stream_path}"
    
    def has_permission(self, user):
        """Check if user has permission to access this camera"""
        # Admin always has access
        if user.is_superuser:
            return True
        # Check if teacher has explicit permission
        return CameraPermission.objects.filter(camera=self, teacher=user).exists()
    
    def get_authorized_teachers(self):
        """Get all teachers with access to this camera"""
        return User.objects.filter(camerapermission__camera=self)


class CameraPermission(models.Model):
    """Permission model to grant teachers access to specific cameras"""
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'userprofile__user_type': 'teacher'})
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='granted_permissions')
    granted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('camera', 'teacher')
        verbose_name = 'Camera Permission'
        verbose_name_plural = 'Camera Permissions'
    
    def __str__(self):
        return f"{self.teacher.username} - {self.camera.name}"


class HeadCountLog(models.Model):
    """Stores head count data from camera feeds for attendance tracking"""
    CAMERA_TYPE_CHOICES = (
        ('rtsp', 'RTSP Camera'),
        ('mobile', 'Mobile Camera'),
    )
    
    # Camera reference (can be RTSP or Mobile camera)
    camera_type = models.CharField(max_length=10, choices=CAMERA_TYPE_CHOICES, default='rtsp')
    camera_id = models.IntegerField()  # ID of Camera or MobileCamera
    camera_name = models.CharField(max_length=100)  # Store name for historical records
    
    # Classroom association (optional - for class-wise grouping)
    classroom = models.ForeignKey(
        'meetings.Classroom', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='head_count_logs'
    )
    
    # Count data
    head_count = models.IntegerField(default=0)
    confidence_score = models.FloatField(default=0.0)  # Average detection confidence
    
    # Timestamp for day-wise, time-wise filtering
    timestamp = models.DateTimeField(auto_now_add=True)
    date = models.DateField()  # Separate date field for easy filtering
    hour = models.IntegerField()  # Hour of the day (0-23)
    
    # Snapshot (optional - stores annotated frame with green boxes)
    snapshot = models.ImageField(upload_to='head_count_snapshots/', blank=True, null=True)
    
    # Metadata
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='head_count_records'
    )
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['date', 'camera_type', 'camera_id']),
            models.Index(fields=['classroom', 'date']),
            models.Index(fields=['hour', 'date']),
        ]
        verbose_name = 'Head Count Log'
        verbose_name_plural = 'Head Count Logs'
    
    def __str__(self):
        return f"{self.camera_name} - {self.head_count} heads @ {self.timestamp}"
    
    def save(self, *args, **kwargs):
        # Auto-populate date and hour from timestamp
        if self.timestamp:
            self.date = self.timestamp.date()
            self.hour = self.timestamp.hour
        super().save(*args, **kwargs)


class HeadCountSession(models.Model):
    """Active head counting session for a camera"""
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('stopped', 'Stopped'),
    )
    
    camera_type = models.CharField(max_length=10, choices=HeadCountLog.CAMERA_TYPE_CHOICES, default='rtsp')
    camera_id = models.IntegerField()
    camera_name = models.CharField(max_length=100)
    classroom = models.ForeignKey(
        'meetings.Classroom', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='head_count_sessions'
    )
    started_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='head_count_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    
    # Interval settings
    capture_interval = models.IntegerField(default=30)  # Seconds between captures
    
    # Summary stats
    total_captures = models.IntegerField(default=0)
    average_head_count = models.FloatField(default=0.0)
    max_head_count = models.IntegerField(default=0)
    min_head_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Head Count Session'
        verbose_name_plural = 'Head Count Sessions'
    
    def __str__(self):
        return f"Session for {self.camera_name} ({self.status})"
