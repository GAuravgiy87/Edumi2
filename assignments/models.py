from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from meetings.models import Classroom

User = get_user_model()


def assignment_question_upload_path(instance, filename):
    """Generate upload path for assignment question files"""
    return f"assignments/{instance.assignment.id}/questions/{filename}"


def assignment_submission_upload_path(instance, filename):
    """Generate upload path for assignment submission files"""
    return f"assignments/{instance.assignment.id}/submissions/{instance.student.username}/{filename}"


class Assignment(models.Model):
    """Model for assignments created by teachers for classrooms"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    total_marks = models.IntegerField(default=100)
    due_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_assignments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-due_date', '-created_at']
        verbose_name = 'Assignment'
        verbose_name_plural = 'Assignments'

    def __str__(self):
        return f"{self.title} ({self.classroom.title})"

    def is_past_due(self):
        """Check if assignment is past due date"""
        return timezone.now() > self.due_date

    def get_submission_status(self, student):
        """Get submission status for a specific student"""
        try:
            submission = self.submissions.get(student=student)
            if submission.submitted_at > self.due_date:
                return 'late'
            return 'submitted'
        except AssignmentSubmission.DoesNotExist:
            if self.is_past_due():
                return 'missing'
            return 'pending'


class AssignmentQuestionFile(models.Model):
    """Model for files attached to assignments (questions, images, PDFs, etc.)"""
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='question_files')
    file = models.FileField(upload_to=assignment_question_upload_path)
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"{self.filename} for {self.assignment.title}"


class AssignmentSubmission(models.Model):
    """Model for student submissions to assignments"""
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('late', 'Late Submission'),
        ('returned', 'Returned'),
    ]

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignment_submissions')
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    marks_obtained = models.IntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    evaluated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='evaluated_submissions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['assignment', 'student']
        ordering = ['-submitted_at']
        verbose_name = 'Assignment Submission'
        verbose_name_plural = 'Assignment Submissions'

    def __str__(self):
        return f"{self.student.username} - {self.assignment.title}"

    def save(self, *args, **kwargs):
        """Set status to late if submitted after due date"""
        if self.submitted_at and self.assignment.due_date:
            if self.submitted_at > self.assignment.due_date:
                self.status = 'late'
            else:
                self.status = 'submitted'
        super().save(*args, **kwargs)


class AssignmentSubmissionFile(models.Model):
    """Model for files submitted by students as part of their assignment"""
    submission = models.ForeignKey(AssignmentSubmission, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to=assignment_submission_upload_path)
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"{self.filename} for {self.submission}"
