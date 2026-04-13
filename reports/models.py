from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class AttendanceReport(models.Model):
    REPORT_TYPES = [
        ('DAILY', 'Daily Report'),
        ('WEEKLY', 'Weekly Report'),
        ('MONTHLY', 'Monthly Report'),
        ('CUSTOM', 'Custom Range'),
    ]

    schedule = models.ForeignKey('attendance.Schedule', on_delete=models.CASCADE)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    data = models.JSONField()  # Store report data as JSON
    generated_at = models.DateTimeField(auto_now_add=True)
    date_from = models.DateField()
    date_to = models.DateField()

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        subject_code = self.schedule.section.subject.code if self.schedule and self.schedule.section else 'N/A'
        return f"{self.get_report_type_display()} - {subject_code} ({self.generated_at.date()})"


class SystemHealthLog(models.Model):
    COMPONENT_CHOICES = [
        ('CAMERA', 'Camera System'),
        ('FACE_RECOGNITION', 'Face Recognition Engine'),
        ('DATABASE', 'Database'),
        ('WEBSOCKET', 'WebSocket Connections'),
        ('CACHE', 'Redis Cache'),
        ('CELERY', 'Background Tasks'),
    ]

    STATUS_CHOICES = [
        ('HEALTHY', 'Healthy'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('OFFLINE', 'Offline'),
    ]

    component = models.CharField(max_length=20, choices=COMPONENT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    message = models.TextField(blank=True)
    metrics = models.JSONField(blank=True, null=True)  # Performance metrics
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['component', 'timestamp']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.component} - {self.get_status_display()} ({self.timestamp})"


class NotificationLog(models.Model):
    NOTIFICATION_TYPES = [
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('PUSH', 'Push Notification'),
        ('IN_APP', 'In-App Notification'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} to {self.user.get_full_name()} - {self.subject}"