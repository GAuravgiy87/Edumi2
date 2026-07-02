from django.contrib import admin
from .models import Assignment, AssignmentQuestionFile, AssignmentSubmission, AssignmentSubmissionFile


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'classroom', 'created_by', 'due_date', 'status', 'total_marks')
    list_filter = ('status', 'classroom', 'created_by', 'due_date')
    search_fields = ('title', 'description', 'instructions')
    date_hierarchy = 'due_date'


@admin.register(AssignmentQuestionFile)
class AssignmentQuestionFileAdmin(admin.ModelAdmin):
    list_display = ('filename', 'assignment', 'file_type', 'uploaded_at')
    list_filter = ('assignment', 'file_type')
    search_fields = ('filename',)


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'status', 'submitted_at', 'marks_obtained')
    list_filter = ('status', 'assignment', 'student')
    search_fields = ('student__username', 'assignment__title')


@admin.register(AssignmentSubmissionFile)
class AssignmentSubmissionFileAdmin(admin.ModelAdmin):
    list_display = ('filename', 'submission', 'file_type', 'uploaded_at')
    list_filter = ('file_type',)
    search_fields = ('filename',)
