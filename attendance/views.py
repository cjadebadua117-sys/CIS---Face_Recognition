import cv2
import numpy as np
from datetime import date, datetime, time, timedelta
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.http import StreamingHttpResponse
from django.shortcuts import render, redirect
from attendance.models import AttendanceRecord, Schedule, AttendanceSession
from faces.models import FaceEncoding, Section
# from faces.models import Person  # TODO: Update to new models after migration


def normalize_subject_code(code):
    return ''.join(str(code).split()).upper() if code else ''


@login_required
def attendance_start(request):
    # Check if student has completed enrollment
    if request.user.is_student and not request.user.is_enrollment_complete():
        messages.warning(request, 'Please complete your subject enrollment before accessing the attendance feature.')
        return redirect('enrollment_start')

    enrolled_subjects = []
    active_sessions = []
    subject_items = []
    face_enrolled = False
    if request.user.is_student:
        enrolled_subjects = list(request.user.get_enrolled_subjects())
        face_enrolled = FaceEncoding.objects.filter(user=request.user, is_active=True).exists()

        # Get active sessions for enrolled subjects by matching normalized subject codes.
        today = date.today()
        enrolled_codes = [subject.code for subject in enrolled_subjects]
        normalized_codes = list({normalize_subject_code(code) for code in enrolled_codes})
        active_sessions = AttendanceSession.objects.filter(
            schedule__section__subject__code__in=(enrolled_codes + normalized_codes),
            date=today,
            is_open=True
        ).select_related('schedule__section__subject')

        # Map enrolled subjects to any active session for direct scan
        for subject in enrolled_subjects:
            normalized_code = normalize_subject_code(subject.code)
            active_session = next(
                (session for session in active_sessions
                 if normalize_subject_code(session.schedule.section.subject.code) == normalized_code),
                None
            )
            subject_items.append({
                'subject': subject,
                'active_session': active_session,
            })

    return render(request, 'attendance/start.html', {
        'enrolled_subjects': enrolled_subjects,
        'active_sessions': active_sessions,
        'subject_items': subject_items,
        'face_enrolled': face_enrolled,
    })


def generate_mjpeg_stream(request):
    """Placeholder for live stream - to be implemented in Phase 4"""
    yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + b'' + b'\r\n'


@login_required
def attendance_stream(request):
    return StreamingHttpResponse(generate_mjpeg_stream(request), content_type='multipart/x-mixed-replace; boundary=frame')


@login_required
def attendance_records(request):
    """Display attendance records with filtering"""
    department = request.GET.get('department')
    section = request.GET.get('section')
    records = AttendanceRecord.objects.select_related(
        'user',
        'schedule__section__subject',
        'schedule__section'
    ).all()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')

    if date_from:
        records = records.filter(date__gte=date_from)
    if date_to:
        records = records.filter(date__lte=date_to)
    if status:
        records = records.filter(status=status)
    if department:
        records = records.filter(user__department__icontains=department)
    if section:
        records = records.filter(schedule__section__name__iexact=section)

    # Show only the current user's attendance records for students.
    if request.user.is_student:
        records = records.filter(user=request.user)
    elif request.user.is_instructor:
        # Instructors see attendance records for their subjects.
        records = records.filter(schedule__section__subject__instructor=request.user)

    records = records.order_by('schedule__section__name', 'date', 'user__last_name', 'user__first_name')

    section_names = Section.objects.order_by('name').values_list('name', flat=True).distinct()

    paginator = Paginator(records, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Calculate summary statistics
    summary_stats = {
        'total': records.count(),
        'present': records.filter(status='PRESENT').count(),
        'absent': records.filter(status='ABSENT').count(),
        'late': records.filter(status='LATE').count(),
        'excused': records.filter(status='EXCUSED').count(),
    }

    history_title = 'Attendance History'
    if request.user.is_instructor:
        history_title = 'Class Attendance History'
    elif request.user.is_student:
        history_title = 'My Attendance History'

    return render(request, 'attendance/records.html', {
        'records': page_obj,
        'page_obj': page_obj,
        'date_from': date_from,
        'date_to': date_to,
        'department': department,
        'section': section,
        'status': status,
        'section_names': section_names,
        'summary_stats': summary_stats,
        'history_title': history_title,
    })
