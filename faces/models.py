from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
import numpy as np

User = get_user_model()


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=10, unique=True, blank=True)
    head = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                           limit_choices_to={'role': 'DEPARTMENT_HEAD'},
                           related_name='headed_departments')

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name


class Subject(models.Model):
    instructor = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='subjects',
        limit_choices_to={'role': 'INSTRUCTOR'},
        null=True, blank=True
    )
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    semester = models.CharField(max_length=20, blank=True, null=True)
    school_year = models.CharField(max_length=20, blank=True, null=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        unique_together = ['code', 'semester', 'school_year']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Section(models.Model):
    subject = models.ForeignKey(
        Subject, 
        on_delete=models.CASCADE,
        related_name='sections'
    )
    name = models.CharField(max_length=20)  # e.g. "Section A"
    schedule_day = models.CharField(max_length=20)  # e.g. "Monday"
    schedule_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ['subject', 'name']

    def __str__(self):
        return f"{self.subject.code} - {self.name}"


class FaceEncoding(models.Model):
    ANGLE_CHOICES = [
        ('FRONT', 'Front'),
        ('LEFT', 'Left Profile'),
        ('RIGHT', 'Right Profile'),
        ('UP', 'Up Angle'),
        ('DOWN', 'Down Angle'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='face_encodings')
    encoding = models.BinaryField()  # 128-dimensional face encoding as binary data
    angle = models.CharField(max_length=10, choices=ANGLE_CHOICES, default='FRONT')
    quality_score = models.FloatField(default=0.0)  # 0.0 to 1.0
    is_liveness_verified = models.BooleanField(default=False)
    liveness_method = models.CharField(max_length=50, blank=True)  # blink, texture, etc.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user', 'angle']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['quality_score']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_angle_display()} ({self.quality_score:.2f})"

    def save(self, *args, **kwargs):
        # Validate encoding is 128-dimensional
        if self.encoding:
            encoding_array = np.frombuffer(self.encoding, dtype=np.float64)
            if len(encoding_array) != 128:
                raise ValidationError("Face encoding must be 128-dimensional")
        super().save(*args, **kwargs)

    @property
    def encoding_array(self):
        """Convert binary encoding back to numpy array"""
        return np.frombuffer(self.encoding, dtype=np.float64)


class EnrollmentRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='reviewed_enrollments')
    rejection_reason = models.TextField(blank=True)
    appeal_message = models.TextField(blank=True)
    appeal_evidence = models.FileField(upload_to='enrollment/appeals/', blank=True, null=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_status_display()}"

    def approve(self, reviewer):
        self.status = 'APPROVED'
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewer
        self.save()
        # Update user's enrollment status
        self.user.is_enrolled = True
        self.user.save()

    def reject(self, reviewer, reason):
        self.status = 'REJECTED'
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewer
        self.rejection_reason = reason
        self.save()
