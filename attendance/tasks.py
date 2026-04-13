from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import AttendanceRecord, Schedule
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_attendance_notification(user_email, subject_name, status, check_in_time):
    """Send email notification for attendance check-in"""
    try:
        subject = f'Attendance Recorded: {subject_name}'
        message = f"""
        Dear Student,

        Your attendance has been recorded for {subject_name}.

        Status: {status}
        Check-in Time: {check_in_time.strftime('%Y-%m-%d %H:%M:%S')}

        If you believe this is incorrect, please contact your instructor or submit an appeal through the system.

        Best regards,
        DMMMSU Face Recognition Attendance System
        """

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
            fail_silently=False,
        )
        logger.info(f"Attendance notification sent to {user_email}")
    except Exception as e:
        logger.error(f"Failed to send attendance notification to {user_email}: {str(e)}")


@shared_task
def mark_absent_students():
    """Automatically mark students as absent who haven't checked in after grace period"""
    now = timezone.now()
    current_time = now.time()
    current_day = now.strftime('%a').upper()

    # Find active schedules for today - filter in Python since SQLite doesn't support JSON contains
    all_schedules = Schedule.objects.all()
    active_schedules = [s for s in all_schedules if current_day in s.days_of_week]

    for schedule in active_schedules:
        # Calculate the time when students should be marked absent
        absent_time = (
            timezone.datetime.combine(now.date(), schedule.start_time) +
            timezone.timedelta(minutes=schedule.auto_absent_minutes)
        ).time()

        if current_time >= absent_time:
            # Find students who haven't checked in yet
            enrolled_students = schedule.subject.department.customuser_set.filter(
                role='STUDENT',
                is_enrolled=True
            )

            for student in enrolled_students:
                attendance, created = AttendanceRecord.objects.get_or_create(
                    user=student,
                    schedule=schedule,
                    date=now.date(),
                    defaults={'status': 'ABSENT'}
                )

                if created:
                    logger.info(f"Auto-marked {student.get_full_name()} as absent for {schedule.subject.code}")


@shared_task
def generate_attendance_report(schedule_id, date_range=None):
    """Generate detailed attendance report for a schedule"""
    from reports.models import AttendanceReport

    schedule = Schedule.objects.get(id=schedule_id)

    if date_range:
        start_date, end_date = date_range
    else:
        # Default to current month
        now = timezone.now()
        start_date = now.replace(day=1)
        end_date = now

    # Generate report data
    records = AttendanceRecord.objects.filter(
        schedule=schedule,
        date__range=[start_date.date(), end_date.date()]
    ).select_related('user')

    report_data = {
        'schedule': schedule.subject.code,
        'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        'total_students': records.values('user').distinct().count(),
        'present_count': records.filter(status='PRESENT').count(),
        'late_count': records.filter(status='LATE').count(),
        'absent_count': records.filter(status='ABSENT').count(),
        'excused_count': records.filter(status='EXCUSED').count(),
    }

    # Create report record
    AttendanceReport.objects.create(
        schedule=schedule,
        report_type='MONTHLY',
        data=report_data,
        generated_at=timezone.now()
    )

    logger.info(f"Generated attendance report for {schedule.subject.code}")
    return report_data


@shared_task
def cleanup_expired_qr_codes():
    """Clean up expired QR codes"""
    from attendance.models import QRCode

    expired_codes = QRCode.objects.filter(
        expires_at__lt=timezone.now(),
        is_active=True
    )

    count = expired_codes.update(is_active=False)
    logger.info(f"Deactivated {count} expired QR codes")


@shared_task
def process_bulk_enrollment(csv_data, department_id):
    """Process bulk student enrollment from CSV data"""
    from faces.models import Department
    import csv
    import io

    department = Department.objects.get(id=department_id)
    results = {'success': 0, 'errors': []}

    csv_reader = csv.DictReader(io.StringIO(csv_data))

    for row_num, row in enumerate(csv_reader, start=2):
        try:
            # Create user account
            user = CustomUser.objects.create_user(
                username=row['student_id'],
                email=row['email'],
                password=row['password'],  # Should be temporary password
                first_name=row['first_name'],
                last_name=row['last_name'],
                role='STUDENT',
                student_id=row['student_id'],
                department=department.name,
                is_enrolled=False  # Will be enrolled after face capture
            )

            # Create enrollment request
            EnrollmentRequest.objects.create(user=user)

            results['success'] += 1

        except Exception as e:
            results['errors'].append(f"Row {row_num}: {str(e)}")

    logger.info(f"Bulk enrollment completed: {results['success']} success, {len(results['errors'])} errors")
    return results