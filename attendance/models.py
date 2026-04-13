from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from geopy.distance import geodesic
from django.conf import settings
import uuid

User = get_user_model()


class Schedule(models.Model):
    DAYS_OF_WEEK = [
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
        ('SAT', 'Saturday'),
        ('SUN', 'Sunday'),
    ]

    section = models.ForeignKey('faces.Section', on_delete=models.CASCADE, related_name='schedules', null=True, blank=True)
    day_of_week = models.CharField(max_length=20, choices=DAYS_OF_WEEK, null=True, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)
    grace_period_minutes = models.PositiveIntegerField(default=15)
    auto_absent_minutes = models.PositiveIntegerField(default=30)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.section.subject.code} - {self.section.name} - {self.get_day_of_week_display()} {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"

    def is_active_now(self):
        now = timezone.now()
        current_time = now.time()
        current_day = now.strftime('%a').upper()

        return (current_day == self.day_of_week and
                self.start_time <= current_time <= self.end_time)

    def get_status_for_time(self, check_time):
        """Determine attendance status based on check-in time"""
        if check_time <= self.start_time:
            return 'PRESENT'
        elif check_time <= (timezone.datetime.combine(timezone.date.today(), self.start_time) +
                           timezone.timedelta(minutes=self.grace_period_minutes)).time():
            return 'LATE'
        else:
            return 'ABSENT'


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('LATE', 'Late'),
        ('ABSENT', 'Absent'),
        ('EXCUSED', 'Excused'),
        ('PENDING', 'Pending Review'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='attendance_records', null=True, blank=True)
    date = models.DateField(default=timezone.now)
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PRESENT')

    # Location data for geofencing
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_within_geofence = models.BooleanField(default=True)

    # Face recognition data
    confidence_score = models.FloatField(null=True, blank=True)
    face_encoding_used = models.ForeignKey('faces.FaceEncoding', on_delete=models.SET_NULL,
                                         null=True, blank=True)

    # Manual override
    manually_marked = models.BooleanField(default=False)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='marked_attendance')

    # Appeal system
    appeal_requested = models.BooleanField(default=False)
    appeal_reason = models.TextField(blank=True)
    appeal_evidence = models.FileField(upload_to='attendance/appeals/', blank=True, null=True)
    appeal_status = models.CharField(max_length=20, choices=[
        ('NONE', 'No Appeal'),
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ], default='NONE')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-check_in_time']
        unique_together = ['user', 'schedule', 'date']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['schedule', 'date']),
            models.Index(fields=['status']),
            models.Index(fields=['date']),
            models.Index(fields=['latitude', 'longitude']),
        ]

    def __str__(self):
        subject_code = self.schedule.section.subject.code if self.schedule and self.schedule.section else 'N/A'
        return f"{self.user.get_full_name()} - {subject_code} on {self.date}"

    def save(self, *args, **kwargs):
        # Validate geofencing if coordinates provided
        if self.latitude and self.longitude:
            campus_coords = (settings.NLUC_LATITUDE, settings.NLUC_LONGITUDE)
            user_coords = (float(self.latitude), float(self.longitude))
            distance = geodesic(campus_coords, user_coords).meters
            self.is_within_geofence = distance <= settings.GEOFENCE_RADIUS_METERS

        # Auto-determine status if not manually marked
        if not self.manually_marked and self.check_in_time:
            self.status = self.schedule.get_status_for_time(self.check_in_time.time())

        super().save(*args, **kwargs)

    @property
    def duration(self):
        """Calculate attendance duration in minutes"""
        if self.check_in_time and self.check_out_time:
            return (self.check_out_time - self.check_in_time).total_seconds() / 60
        return None

    def submit_appeal(self, reason, evidence=None):
        """Submit an appeal for this attendance record"""
        self.appeal_requested = True
        self.appeal_reason = reason
        self.appeal_status = 'PENDING'
        if evidence:
            self.appeal_evidence = evidence
        self.save()


class AttendanceAppeal(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    attendance_record = models.OneToOneField(AttendanceRecord, on_delete=models.CASCADE,
                                           related_name='appeal_details')
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submitted_appeals')
    reason = models.TextField()
    evidence = models.FileField(upload_to='attendance/appeal_evidence/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='reviewed_appeals')
    review_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Appeal for {self.attendance_record} by {self.submitted_by.get_full_name()}"

    def approve(self, reviewer, notes=''):
        self.status = 'APPROVED'
        self.reviewed_by = reviewer
        self.review_notes = notes
        self.reviewed_at = timezone.now()
        self.save()

        # Update the attendance record
        self.attendance_record.status = 'EXCUSED'
        self.attendance_record.appeal_status = 'APPROVED'
        self.attendance_record.save()

    def reject(self, reviewer, notes=''):
        self.status = 'REJECTED'
        self.reviewed_by = reviewer
        self.review_notes = notes
        self.reviewed_at = timezone.now()
        self.save()

        self.attendance_record.appeal_status = 'REJECTED'
        self.attendance_record.save()


class AttendanceSession(models.Model):
    """Teacher-controlled attendance session for a specific class"""
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='attendance_sessions')
    date = models.DateField(default=timezone.now)
    is_open = models.BooleanField(default=False)
    opened_at = models.DateTimeField(null=True, blank=True)
    opened_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='opened_sessions')
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='closed_sessions')
    grace_period_minutes = models.PositiveIntegerField(default=15)

    class Meta:
        unique_together = ['schedule', 'date']
        ordering = ['-date', '-opened_at']

    def __str__(self):
        subject_code = self.schedule.section.subject.code if self.schedule and self.schedule.section else 'N/A'
        return f"{subject_code} - {self.date} ({'Open' if self.is_open else 'Closed'})"

    def open_session(self, user):
        """Open the attendance session"""
        self.is_open = True
        self.opened_at = timezone.now()
        self.opened_by = user
        self.save()

    def close_session(self, user):
        """Close the attendance session"""
        self.is_open = False
        self.closed_at = timezone.now()
        self.closed_by = user
        self.save()
        self.mark_absent_students()

    def mark_absent_students(self):
        """Mark all enrolled students absent if they did not check in before session close."""
        from accounts.models import StudentEnrollment

        faces_subject = self.schedule.section.subject
        subject_code = getattr(faces_subject, 'code', None)
        section_name = getattr(self.schedule.section, 'name', None)

        enrolled_students = StudentEnrollment.objects.filter(
            subject__code=subject_code,
            subject__section=section_name
        ).select_related('student')

        if not enrolled_students.exists() and subject_code:
            enrolled_students = StudentEnrollment.objects.filter(
                subject__code=subject_code
            ).select_related('student')

        for enrollment in enrolled_students:
            student = enrollment.student
            record = AttendanceRecord.objects.filter(
                user=student,
                schedule=self.schedule,
                date=self.date
            ).first()

            if record:
                if record.check_in_time is None and record.status != 'ABSENT':
                    record.status = 'ABSENT'
                    record.save()
                continue

            AttendanceRecord.objects.create(
                user=student,
                schedule=self.schedule,
                date=self.date,
                status='ABSENT'
            )

    def get_time_elapsed(self):
        """Get time elapsed since session opened"""
        if self.opened_at:
            elapsed = timezone.now() - self.opened_at
            return elapsed.total_seconds() / 60  # Return minutes
        return 0

    def get_schedule_end_datetime(self):
        """Get the scheduled end datetime for this session"""
        end_datetime = timezone.datetime.combine(self.date, self.schedule.end_time)
        if timezone.is_naive(end_datetime):
            end_datetime = timezone.make_aware(end_datetime, timezone.get_current_timezone())
        return end_datetime

    def is_after_schedule_end(self):
        """Return whether the session has passed the scheduled end time."""
        if not self.schedule or not self.opened_at:
            return False
        return timezone.now() > self.get_schedule_end_datetime()

    @property
    def camera_enabled(self):
        """Return whether the camera should be available for this session."""
        if not self.is_open or not self.opened_at:
            return False
        if self.is_after_schedule_end():
            return False
        return timezone.now() <= self.opened_at + timezone.timedelta(minutes=self.grace_period_minutes)

    def get_status_for_scan(self):
        """Determine if scan should be marked as Present, Late, or Absent"""
        if not self.is_open or not self.opened_at:
            return None

        if self.is_after_schedule_end():
            return 'ABSENT'

        elapsed_minutes = self.get_time_elapsed()
        if elapsed_minutes <= self.grace_period_minutes:
            return 'PRESENT'
        elif elapsed_minutes <= self.schedule.auto_absent_minutes:
            return 'LATE'
        else:
            return 'ABSENT'

    def get_countdown_info(self):
        """Get countdown information for the session"""
        if not self.is_open or not self.opened_at:
            return None

        elapsed = self.get_time_elapsed()
        camera_remaining = self.grace_period_minutes - elapsed
        late_remaining = self.schedule.auto_absent_minutes - elapsed

        return {
            'elapsed_minutes': int(elapsed),
            'camera_remaining_minutes': int(max(0, camera_remaining)),
            'late_remaining_minutes': int(max(0, late_remaining)),
            'is_in_grace_period': camera_remaining > 0,
            'is_in_late_window': elapsed <= self.schedule.auto_absent_minutes,
            'is_after_schedule_end': self.is_after_schedule_end(),
            'time_until_late': int(camera_remaining) if camera_remaining > 0 else 0
        }


class QRCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='qr_codes')
    code = models.UUIDField(default=uuid.uuid4, unique=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"QR Code for {self.user.get_full_name()}"

    def is_expired(self):
        return timezone.now() > self.expires_at

    def generate_new_code(self):
        """Generate a new QR code with 24-hour expiration"""
        self.code = uuid.uuid4()
        self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        self.is_active = True
        self.save()
        return self.code
