from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
import re


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('STUDENT', 'Student'),
        ('INSTRUCTOR', 'Instructor'),
        ('DEPARTMENT_HEAD', 'Department Head'),
        ('REGISTRAR', 'Registrar'),
        ('SYSTEM_ADMIN', 'System Administrator'),
        ('GUARD', 'Security Guard'),
    ]

    YEAR_LEVEL_CHOICES = [
        ('1', 'Year 1'),
        ('2', 'Year 2'),
        ('3', 'Year 3'),
        ('4', 'Year 4'),
    ]

    SECTION_CHOICES = [
        ('A', 'Section A'),
        ('B', 'Section B'),
        ('C', 'Section C'),
    ]

    ENROLLMENT_STATUS_CHOICES = [
        ('NOT_ENROLLED', 'Not Enrolled'),
        ('PENDING', 'Pending Enrollment'),
        ('REGULAR', 'Regular'),
        ('IRREGULAR', 'Irregular'),
    ]

    email = models.EmailField(unique=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='STUDENT')
    employee_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    student_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True)
    is_enrolled = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=15, blank=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    login_attempts = models.PositiveIntegerField(default=0)
    lockout_until = models.DateTimeField(blank=True, null=True)
    
    # New fields for enrollment
    year_level = models.CharField(max_length=1, choices=YEAR_LEVEL_CHOICES, blank=True, null=True)
    section = models.CharField(max_length=1, choices=SECTION_CHOICES, blank=True, null=True)
    enrollment_status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS_CHOICES, default='NOT_ENROLLED')
    enrollment_completed_date = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        permissions = [
            ('can_enroll_faces', 'Can enroll face data'),
            ('can_mark_attendance', 'Can mark attendance manually'),
            ('can_view_reports', 'Can view attendance reports'),
            ('can_manage_users', 'Can manage user accounts'),
            ('can_access_admin_panel', 'Can access admin panel'),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.email}) - {self.get_role_display()}"

    @property
    def is_student(self):
        # Only users explicitly assigned the STUDENT role should act as students.
        # Superusers and staff users should never be treated as student accounts.
        return self.role == 'STUDENT' and not (self.is_superuser or self.is_staff)

    @property
    def is_instructor(self):
        return self.role == 'INSTRUCTOR'

    @property
    def is_department_head(self):
        return self.role == 'DEPARTMENT_HEAD'

    @property
    def is_registrar(self):
        return self.role == 'REGISTRAR'

    @property
    def is_system_admin(self):
        return self.role == 'SYSTEM_ADMIN'

    @property
    def is_guard(self):
        return self.role == 'GUARD'

    def can_enroll_faces(self):
        return self.is_student or self.is_system_admin or self.is_registrar

    def can_mark_attendance(self):
        return self.is_instructor or self.is_system_admin or self.is_department_head

    def can_manage_users(self):
        return self.is_system_admin or self.is_registrar or self.is_department_head

    def is_locked_out(self):
        if self.lockout_until and timezone.now() < self.lockout_until:
            return True
        return False

    def increment_login_attempts(self):
        self.login_attempts += 1
        if self.login_attempts >= 5:
            self.lockout_until = timezone.now() + timezone.timedelta(minutes=15)
        self.save()

    def reset_login_attempts(self):
        self.login_attempts = 0
        self.lockout_until = None
        self.save()

    def get_required_subjects(self):
        """Get required subjects for the student's year level and section"""
        if not self.year_level or not self.section:
            return Subject.objects.none()
        
        return Subject.objects.filter(
            year_level=self.year_level,
            section=self.section
        )

    def get_enrolled_subjects(self):
        """Get subjects the student is enrolled in"""
        return Subject.objects.filter(
            studentenrollment__student=self
        ).distinct()

    def update_enrollment_status(self):
        """Update enrollment status to REGULAR or IRREGULAR based on enrollments"""
        if self.enrollment_status == 'NOT_ENROLLED':
            return
        
        if not self.year_level or not self.section:
            self.enrollment_status = 'PENDING'
            self.save()
            return
        
        required_subjects = self.get_required_subjects()
        enrolled_subjects = self.get_enrolled_subjects()
        
        if not required_subjects.exists():
            self.enrollment_status = 'PENDING'
            self.save()
            return
        
        # Check if student enrolled in subjects outside their year
        all_enrolled = enrolled_subjects
        outside_year = all_enrolled.exclude(year_level=self.year_level)
        
        if outside_year.exists():
            # Student enrolled in subjects from different years - IRREGULAR
            self.enrollment_status = 'IRREGULAR'
        elif required_subjects.count() == enrolled_subjects.filter(year_level=self.year_level, section=self.section).count():
            # Student enrolled in all required subjects - REGULAR
            self.enrollment_status = 'REGULAR'
        else:
            # Student missing some subjects - IRREGULAR
            self.enrollment_status = 'IRREGULAR'
        
        self.save()

    def is_enrollment_complete(self):
        """Check if student has completed enrollment process"""
        return self.enrollment_status in ['REGULAR', 'IRREGULAR']


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('LOGIN_FAILED', 'Login Failed'),
        ('PASSWORD_CHANGE', 'Password Change'),
        ('PROFILE_UPDATE', 'Profile Update'),
        ('FACE_ENROLLMENT', 'Face Enrollment'),
        ('ATTENDANCE_MARK', 'Attendance Marked'),
        ('USER_CREATE', 'User Created'),
        ('USER_UPDATE', 'User Updated'),
        ('USER_DELETE', 'User Deleted'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    details = models.JSONField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'action']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        return f"{self.user} - {self.get_action_display()} at {self.timestamp}"


class PasswordHistory(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='password_history')
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'password_hash']

    def __str__(self):
        return f"{self.user} password change at {self.created_at}"


class PasswordResetRequest(models.Model):
    requested_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='password_reset_requests')
    requested_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_password_requests'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    notified = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        status = 'Resolved' if self.is_resolved else 'Pending'
        return f"Password reset request by {self.requested_by} ({status})"


class Subject(models.Model):
    """Subject model for BSIS program"""
    YEAR_LEVEL_CHOICES = [
        ('1', 'Year 1'),
        ('2', 'Year 2'),
        ('3', 'Year 3'),
        ('4', 'Year 4'),
    ]

    SECTION_CHOICES = [
        ('A', 'Section A'),
        ('B', 'Section B'),
        ('C', 'Section C'),
    ]

    code = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    year_level = models.CharField(max_length=1, choices=YEAR_LEVEL_CHOICES)
    section = models.CharField(max_length=1, choices=SECTION_CHOICES)
    description = models.TextField(blank=True)
    units = models.PositiveIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['year_level', 'section', 'code']
        unique_together = ['code', 'year_level', 'section']
        indexes = [
            models.Index(fields=['year_level', 'section']),
        ]

    def __str__(self):
        return f"{self.code} - {self.title} ({self.get_year_level_display()} {self.get_section_display()})"


class StudentEnrollment(models.Model):
    """Track student enrollment in subjects"""
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='enrollments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    enrolled_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['student', 'subject']
        ordering = ['subject__year_level', 'subject__section', 'subject__code']
        indexes = [
            models.Index(fields=['student', 'is_active']),
        ]

    def __str__(self):
        return f"{self.student.username} - {self.subject.code}"
