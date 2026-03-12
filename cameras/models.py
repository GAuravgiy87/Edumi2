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
        if self.username and self.password:
            return f"rtsp://{self.username}:{self.password}@{self.ip_address}:{self.port}{self.stream_path}"
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
