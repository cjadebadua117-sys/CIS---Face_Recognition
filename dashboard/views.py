from datetime import date, datetime, timedelta
from collections import OrderedDict
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Count, Case, When, IntegerField
from django.contrib import messages
from django.http import HttpResponse
from attendance.models import AttendanceRecord, Schedule, AttendanceSession
from faces.models import FaceEncoding, Subject, Section
from faces.forms import SubjectForm, SectionForm
from django.utils import timezone


@login_required
def dashboard_view(request):
    """Smart dashboard router - directs to role-specific dashboards"""
    user = request.user
    
    # Determine user role and redirect to appropriate dashboard
    if hasattr(user, 'role'):
        if user.is_superuser or user.role == 'SYSTEM_ADMIN':
            return redirect('admin_dashboard')
        elif user.role in ['INSTRUCTOR', 'DEPARTMENT_HEAD', 'REGISTRAR']:
            return redirect('instructor_dashboard')
    
    # Default to student dashboard for unknown roles
    return redirect('student_dashboard')


@login_required
def student_dashboard(request):
    """Student dashboard with attendance stats, schedule, and enrollment status"""
    user = request.user
    today = date.today()
    current_month_start = today.replace(day=1)
    next_month = (current_month_start + timedelta(days=32)).replace(day=1)
    current_month_end = next_month - timedelta(days=1)
    
    # === ATTENDANCE STATISTICS ===
    month_records = AttendanceRecord.objects.filter(
        user=user,
        date__range=[current_month_start, current_month_end]
    )
    
    present_count = month_records.filter(status='PRESENT').count()
    late_count = month_records.filter(status='LATE').count()
    absent_count = month_records.filter(status='ABSENT').count()
    excused_count = month_records.filter(status='EXCUSED').count()
    total_days = present_count + late_count + absent_count + excused_count
    
    attendance_percentage = (present_count / total_days * 100) if total_days > 0 else 0
    
    # Current streak (consecutive present/late days)
    today_records = AttendanceRecord.objects.filter(user=user, date=today)
    current_streak = 0
    check_date = today
    while True:
        streak_record = AttendanceRecord.objects.filter(user=user, date=check_date).exists()
        if streak_record and AttendanceRecord.objects.filter(user=user, date=check_date, status__in=['PRESENT', 'LATE']).exists():
            current_streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    
    # === CALENDAR DATA ===
    # Get all records for current month for calendar display
    calendar_records = AttendanceRecord.objects.filter(
        user=user,
        date__range=[current_month_start, current_month_end]
    ).values('date', 'status')
    
    calendar_dict = {record['date']: record['status'] for record in calendar_records}
    
    # Build calendar grid (7 columns for days of week)
    calendar_weeks = []
    current_date = current_month_start
    week = []
    
    # Add padding for first week
    days_before = current_date.weekday()
    for _ in range(days_before):
        week.append(None)
    
    while current_date <= current_month_end:
        week.append({
            'date': current_date,
            'status': calendar_dict.get(current_date),
            'day': current_date.day
        })
        if len(week) == 7:
            calendar_weeks.append(week)
            week = []
        current_date += timedelta(days=1)
    
    # Pad last week if needed
    if week:
        while len(week) < 7:
            week.append(None)
        calendar_weeks.append(week)
    
    # === TODAY'S SCHEDULE ===
    today_weekday = today.strftime('%a').upper()
    enrolled_subjects = user.get_enrolled_subjects()
    enrolled_subject_codes = enrolled_subjects.values_list('code', flat=True)
    all_schedules = Schedule.objects.filter(section__subject__code__in=enrolled_subject_codes).order_by('start_time')
    today_schedules = [s for s in all_schedules if s.day_of_week == today_weekday]
    
    schedule_with_countdown = []
    current_time = timezone.now().time()
    
    for schedule in today_schedules:
        if schedule.start_time > current_time:
            # Calculate time to class
            time_diff = timezone.datetime.combine(today, schedule.start_time) - timezone.datetime.combine(today, current_time)
            minutes_remaining = int(time_diff.total_seconds() / 60)
            status = 'UPCOMING'
        elif schedule.end_time > current_time:
            status = 'IN_PROGRESS'
            minutes_remaining = 0
        else:
            status = 'COMPLETED'
            minutes_remaining = 0
        
        schedule_with_countdown.append({
            'schedule': schedule,
            'status': status,
            'minutes_remaining': minutes_remaining
        })
    
    # === AT-RISK SUBJECTS (< 80% attendance) ===
    at_risk_subjects = []
    # TODO: Implement after adding Subject model integration
    
    # === FACE ENROLLMENT STATUS ===
    face_enrolled = FaceEncoding.objects.filter(user=user).exists()
    
    # === ENROLLMENT STATUS ===
    enrollment_complete = user.is_enrollment_complete()
    enrollment_status = user.get_enrollment_status_display()
    
    # === WEEKLY TREND ===
    trend = OrderedDict()
    trend_percentages = OrderedDict()

    for offset in range(6, -1, -1):
        current_day = today - timedelta(days=offset)
        day_records = AttendanceRecord.objects.filter(
            user=user,
            date=current_day
        )

        total_records = day_records.count()
        present_records = day_records.filter(status__in=['PRESENT', 'LATE']).count()

        # Calculate percentage
        percentage = int((present_records / total_records * 100)) if total_records > 0 else 0
        trend_percentages[current_day.strftime('%a')] = percentage

        # For binary display (backward compatibility)
        trend[current_day.strftime('%a')] = 1 if present_records > 0 else 0

    trend_data = [{'label': label, 'value': value} for label, value in trend.items()]

    # === SUBJECT ATTENDANCE BREAKDOWN ===
    subject_summary = {}
    subject_records = month_records.filter(schedule__isnull=False).select_related('schedule__section__subject')
    for record in subject_records:
        subj = record.schedule.section.subject
        key = subj.code
        subject_summary.setdefault(key, {
            'subject': subj,
            'present': 0,
            'total': 0,
        })
        if record.status in ['PRESENT', 'LATE', 'EXCUSED']:
            subject_summary[key]['present'] += 1
        subject_summary[key]['total'] += 1

    subject_attendance = []
    for data in subject_summary.values():
        percent = int(data['present'] / data['total'] * 100) if data['total'] else 0
        subject_attendance.append({
            'code': data['subject'].code,
            'name': data['subject'].name,
            'percent': percent,
            'accent': 'amber' if percent < 75 else 'cyan',
        })

    if not subject_attendance:
        subject_attendance = [{
            'code': 'N/A',
            'name': 'No subject data available',
            'percent': 0,
            'accent': 'cyan',
        }]

    # === RECOGNITION EVENT LOG ===
    recognition_log = []
    recent_logs = AttendanceRecord.objects.filter(
        user=user,
        schedule__isnull=False,
        check_in_time__isnull=False
    ).select_related('schedule__section__subject').order_by('-check_in_time')[:4]

    for rec in recent_logs:
        timestamp = rec.check_in_time.strftime('%H:%M')
        subject_code = 'UNKNOWN'
        if rec.schedule and rec.schedule.section and rec.schedule.section.subject:
            subject_code = rec.schedule.section.subject.code
        message = f"{user.first_name or user.username} — Recognized · {subject_code}"
        recognition_log.append({
            'time': timestamp,
            'message': message,
            'type': 'recognized',
        })

    recognition_log += [
        {'time': '09:02', 'message': 'Face detection engine ready', 'type': 'system'},
        {'time': '08:45', 'message': 'Camera stream initialized', 'type': 'system'},
    ]

    # === NEXT CLASS INDICATOR ===
    next_class = None
    current_datetime = timezone.now()
    current_time = current_datetime.time()

    # Find the next upcoming class
    for schedule in today_schedules:
        if schedule.start_time > current_time:
            # Calculate time until class
            class_datetime = timezone.datetime.combine(today, schedule.start_time)
            time_diff = class_datetime - current_datetime
            hours_until = int(time_diff.total_seconds() / 3600)
            minutes_until = int((time_diff.total_seconds() % 3600) / 60)

            next_class = {
                'schedule': schedule,
                'hours_until': hours_until,
                'minutes_until': minutes_until,
                'time_until_str': f"{hours_until}h {minutes_until}m" if hours_until > 0 else f"{minutes_until}m"
            }
            break

    # If no classes today, find next class in future
    if not next_class:
        for offset in range(1, 8):  # Check next 7 days
            future_date = today + timedelta(days=offset)
            future_weekday = future_date.strftime('%a').upper()
            future_schedules = [s for s in all_schedules if future_weekday in s.days_of_week]

            if future_schedules:
                next_schedule = future_schedules[0]  # Get first class of that day
                days_until = offset
                next_class = {
                    'schedule': next_schedule,
                    'days_until': days_until,
                    'date': future_date,
                    'time_until_str': f"in {days_until} day{'s' if days_until > 1 else ''}"
                }
                break

    year_section = f"BSIS {user.get_year_level_display()} · {user.get_section_display()}" if user.year_level and user.section else 'Year / Section not set'
    student_status = user.get_enrollment_status_display() if hasattr(user, 'get_enrollment_status_display') else 'Regular'

    context = {
        'today': today,
        'current_month': current_month_start,
        'attendance_percentage': round(attendance_percentage, 1),
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'excused_count': excused_count,
        'current_streak': current_streak,
        'calendar_weeks': calendar_weeks,
        'month_name': current_month_start.strftime('%B %Y'),
        'today_schedules': schedule_with_countdown,
        'face_enrolled': face_enrolled,
        'at_risk_subjects': at_risk_subjects,
        'trend_labels': list(trend.keys()),
        'trend_values': list(trend_percentages.values()),  # Use percentages instead of binary
        'trend_data': trend_data,
        'next_class': next_class,
        'subject_attendance': subject_attendance,
        'recognition_log': recognition_log,
        'year_section': year_section,
        'student_status': student_status,
        'enrollment_complete': enrollment_complete,
        'enrollment_status': enrollment_status,
        'year_level': user.get_year_level_display() if user.year_level else 'Not Selected',
        'section': user.get_section_display() if user.section else 'Not Selected',
    }

    return render(request, 'dashboard/student_dashboard.html', context)


@login_required
def instructor_dashboard(request):
    return redirect('instructor_subjects')


@login_required
def instructor_subjects(request):
    if request.user.role != 'INSTRUCTOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    subjects = Subject.objects.filter(instructor=request.user).order_by('-is_archived', 'name')
    today_name = date.today().strftime('%A')
    
    context = {
        'subjects': subjects,
        'today_name': today_name,
    }
    return render(request, 'dashboard/instructor_subjects.html', context)


@login_required
def add_subject(request):
    if request.user.role != 'INSTRUCTOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.instructor = request.user
            subject.save()
            messages.success(request, 'Subject added successfully.')
            return redirect('instructor_subjects')
    else:
        form = SubjectForm()
    
    context = {
        'form': form,
        'title': 'Add New Subject',
    }
    return render(request, 'dashboard/subject_form.html', context)


@login_required
def edit_subject(request, subject_id):
    if request.user.role != 'INSTRUCTOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    subject = get_object_or_404(Subject, id=subject_id, instructor=request.user)
    
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject updated successfully.')
            return redirect('instructor_subjects')
    else:
        form = SubjectForm(instance=subject)
    
    context = {
        'form': form,
        'subject': subject,
        'title': 'Edit Subject',
    }
    return render(request, 'dashboard/subject_form.html', context)


@login_required
def archive_subject(request, subject_id):
    if request.user.role != 'INSTRUCTOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    subject = get_object_or_404(Subject, id=subject_id, instructor=request.user)
    subject.is_archived = not subject.is_archived
    subject.save()
    action = 'archived' if subject.is_archived else 'unarchived'
    messages.success(request, f'Subject {action} successfully.')
    return redirect('instructor_subjects')


@login_required
def delete_subject(request, subject_id):
    if request.user.role != 'INSTRUCTOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    subject = get_object_or_404(Subject, id=subject_id, instructor=request.user)
    if request.method == 'POST':
        subject.delete()
        messages.success(request, 'Subject deleted successfully.')
    else:
        messages.error(request, 'Invalid request.')
    return redirect('instructor_subjects')


@login_required
def edit_section(request, subject_id, section_id):
    if request.user.role != 'INSTRUCTOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    subject = get_object_or_404(Subject, id=subject_id, instructor=request.user)
    section = get_object_or_404(Section, id=section_id, subject=subject)

    if request.method == 'POST':
        form = SectionForm(request.POST, instance=section)
        if form.is_valid():
            section = form.save(commit=False)
            section.name = section.name.strip()
            if Section.objects.filter(subject=subject, name__iexact=section.name).exclude(id=section.id).exists():
                form.add_error('name', 'A section with this name already exists for this subject.')
            else:
                section.save()
                messages.success(request, 'Section updated successfully.')
                return redirect('instructor_subjects')
    else:
        form = SectionForm(instance=section)

    context = {
        'form': form,
        'subject': subject,
        'section': section,
        'title': 'Edit Section',
    }
    return render(request, 'dashboard/section_form.html', context)


@login_required
def delete_section(request, subject_id, section_id):
    if request.user.role != 'INSTRUCTOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    subject = get_object_or_404(Subject, id=subject_id, instructor=request.user)
    section = get_object_or_404(Section, id=section_id, subject=subject)
    if request.method == 'POST':
        section.delete()
        messages.success(request, 'Section deleted successfully.')
    else:
        messages.error(request, 'Invalid request.')
    return redirect('instructor_subjects')


@login_required
def add_section(request, subject_id):
    if request.user.role != 'INSTRUCTOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    subject = get_object_or_404(Subject, id=subject_id, instructor=request.user)
    
    if request.method == 'POST':
        form = SectionForm(request.POST)
        if form.is_valid():
            section = form.save(commit=False)
            section.subject = subject
            section.name = section.name.strip()
            if Section.objects.filter(subject=subject, name__iexact=section.name).exists():
                form.add_error('name', 'A section with this name already exists for this subject.')
            else:
                section.save()

                # Ensure a Schedule exists for the section so attendance can be opened.
                day_map = {
                    'Monday': 'MON',
                    'Tuesday': 'TUE',
                    'Wednesday': 'WED',
                    'Thursday': 'THU',
                    'Friday': 'FRI',
                    'Saturday': 'SAT',
                    'Sunday': 'SUN',
                }
                day_code = day_map.get(section.schedule_day)
                if day_code:
                    start_time = section.schedule_time
                    end_time = (datetime.combine(timezone.now().date(), start_time) + timedelta(hours=1)).time()
                    Schedule.objects.get_or_create(
                        section=section,
                        day_of_week=day_code,
                        defaults={
                            'start_time': start_time,
                            'end_time': end_time,
                            'room': section.room,
                        }
                    )

                messages.success(request, 'Section added successfully.')
                return redirect('instructor_subjects')
    else:
        form = SectionForm()
    
    context = {
        'form': form,
        'subject': subject,
        'title': 'Add Section',
    }
    return render(request, 'dashboard/section_form.html', context)


@login_required
def open_section_attendance(request, subject_id, section_id):
    if request.user.role != 'INSTRUCTOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    subject = get_object_or_404(Subject, id=subject_id, instructor=request.user)
    section = get_object_or_404(Section, id=section_id, subject=subject)
    today = timezone.localdate()
    day_map = {
        'Monday': 'MON',
        'Tuesday': 'TUE',
        'Wednesday': 'WED',
        'Thursday': 'THU',
        'Friday': 'FRI',
        'Saturday': 'SAT',
        'Sunday': 'SUN',
    }
    section_day_code = day_map.get(section.schedule_day)
    today_code = today.strftime('%a').upper()

    if section_day_code != today_code:
        messages.error(request, 'This section is not scheduled for today. Attendance can only be started on the section schedule day.')
        return redirect('instructor_subjects')

    schedule, _ = Schedule.objects.get_or_create(
        section=section,
        day_of_week=today_code,
        start_time=section.schedule_time,
        defaults={
            'end_time': (datetime.combine(today, section.schedule_time) + timedelta(hours=1)).time(),
            'room': section.room,
        }
    )

    session, created = AttendanceSession.objects.get_or_create(
        schedule=schedule,
        date=today,
        defaults={'is_open': False}
    )

    if session.is_open:
        messages.info(request, 'Attendance session is already open for this section.')
    else:
        session.open_session(request.user)
        messages.success(request, 'Attendance session opened successfully.')

    return redirect('section_attendance', subject_id=subject.id, section_id=section.id)


@login_required
def section_attendance(request, subject_id, section_id):
    if request.user.role != 'INSTRUCTOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    subject = get_object_or_404(Subject, id=subject_id, instructor=request.user)
    section = get_object_or_404(Section, id=section_id, subject=subject)
    
    today = timezone.localdate()
    today_day_code = today.strftime('%a').upper()
    today_schedule = section.schedules.filter(day_of_week=today_day_code).order_by('start_time').first()
    today_session = None

    if not today_schedule and section.schedule_day:
        # Fallback for existing sections without a linked Schedule record.
        day_map = {
            'Monday': 'MON',
            'Tuesday': 'TUE',
            'Wednesday': 'WED',
            'Thursday': 'THU',
            'Friday': 'FRI',
            'Saturday': 'SAT',
            'Sunday': 'SUN',
        }
        if day_map.get(section.schedule_day) == today_day_code:
            today_schedule = Schedule.objects.filter(
                section=section,
                day_of_week=today_day_code,
                start_time=section.schedule_time
            ).first()
            if not today_schedule:
                today_schedule = Schedule.objects.create(
                    section=section,
                    day_of_week=today_day_code,
                    start_time=section.schedule_time,
                    end_time=(datetime.combine(today, section.schedule_time) + timedelta(hours=1)).time(),
                    room=section.room,
                )

    if today_schedule:
        today_session = AttendanceSession.objects.filter(schedule=today_schedule, date=today).first()

    # Get attendance records for this section
    records = AttendanceRecord.objects.filter(
        schedule__section=section
    ).select_related('user', 'schedule').order_by('-date', '-check_in_time')
    
    # Apply filters
    status_filter = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    student_filter = request.GET.get('student')
    
    if status_filter:
        records = records.filter(status=status_filter)
    if date_from:
        records = records.filter(date__gte=date_from)
    if date_to:
        records = records.filter(date__lte=date_to)
    if student_filter:
        records = records.filter(
            Q(user__first_name__icontains=student_filter) |
            Q(user__last_name__icontains=student_filter) |
            Q(user__email__icontains=student_filter)
        )
    
    # Export functionality
    if 'export' in request.GET:
        import csv
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{subject.code}_{section.name}_attendance.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Date', 'Student', 'Time In', 'Status'])
        for record in records:
            writer.writerow([
                record.date,
                record.user.get_full_name(),
                record.check_in_time.strftime('%H:%M:%S') if record.check_in_time else '',
                record.get_status_display()
            ])
        return response
    
    context = {
        'subject': subject,
        'section': section,
        'today_schedule': today_schedule,
        'today_session': today_session,
        'today': today,
        'records': records[:100],  # Limit for display
        'total_records': records.count(),
        'status_choices': AttendanceRecord.STATUS_CHOICES,
    }
    return render(request, 'dashboard/section_attendance.html', context)
