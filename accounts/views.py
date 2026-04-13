from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Count, Case, When, IntegerField
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils import timezone
from django.core.cache import cache
from datetime import date, timedelta
import json
import logging

from accounts.forms import (
    EnhancedLoginForm,
    UserRegistrationForm,
    AdminInstructorForm,
    AdminUserEditForm,
    PasswordResetRequestForm,
    AdminPasswordResetForm,
)
from accounts.models import AuditLog, PasswordHistory, PasswordResetRequest
from faces.models import Subject
from attendance.models import AttendanceRecord

User = get_user_model()
logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Extract client IP from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def check_rate_limit(request, username):
    """Check login rate limiting: 5 failed attempts = 15min lockout"""
    try:
        cache_key = f"login_attempts:{username}"
        lockout_key = f"login_lockout:{username}"
        
        # Check if user is locked out
        if cache.get(lockout_key):
            return False, "Account temporarily locked. Try again in 15 minutes."
        
        # Get failed attempts
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            # Lock account for 15 minutes
            cache.set(lockout_key, True, 900)  # 15 minutes
            return False, "Too many failed attempts. Account locked for 15 minutes."
        
        return True, None
    except Exception:
        # If cache is unavailable, skip rate limiting
        return True, None


def increment_failed_attempts(request, username):
    """Increment failed login attempts and log"""
    try:
        cache_key = f"login_attempts:{username}"
        attempts = cache.get(cache_key, 0)
        cache.set(cache_key, attempts + 1, 3600)  # Expire after 1 hour
    except Exception:
        # If cache is unavailable, skip incrementing
        pass
    
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Log failed attempt
    AuditLog.objects.create(
        user=None,  # Unknown user at this point
        action='LOGIN_FAILED',
        ip_address=ip,
        user_agent=user_agent,
        details={'username': username, 'reason': 'authentication_failed'}
    )


def reset_failed_attempts(username):
    """Reset failed attempts counter on successful login"""
    try:
        cache_key = f"login_attempts:{username}"
        cache.delete(cache_key)
    except Exception:
        # If cache is unavailable, skip reset
        pass


def create_audit_log(user, action, request, details=None):
    """Create audit log entry for user action"""
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    AuditLog.objects.create(
        user=user,
        action=action,
        ip_address=ip,
        user_agent=user_agent,
        details=details or {'action': action}
    )


@ensure_csrf_cookie
def get_csrf_token(request):
    """Endpoint to get CSRF token for AJAX requests"""
    return JsonResponse({'csrfToken': request.META.get('CSRF_COOKIE', '')})


@require_http_methods(["GET", "POST"])
def login_view(request):
    """Enhanced login view with AJAX/HTMX support"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        # Check rate limiting
        username = request.POST.get('username', '')
        can_attempt, error_msg = check_rate_limit(request, username)
        
        if not can_attempt:
            if request.headers.get('HX-Request'):
                return HttpResponse(f'<div class="alert alert-danger">{error_msg}</div>', status=429)
            messages.error(request, error_msg)
            form = EnhancedLoginForm(request)
            return render(request, 'accounts/login.html', {'form': form}, status=429)

        form = EnhancedLoginForm(request, data=request.POST)
        
        if form.is_valid():
            user = form.get_user()
            reset_failed_attempts(username)
            
            # Handle "Remember Me"
            if form.cleaned_data.get('remember_me'):
                request.session.set_expiry(timedelta(days=30))
            else:
                request.session.set_expiry(timedelta(hours=8))
            
            login(request, user)
            create_audit_log(user, 'LOGIN', request)

            resolved_requests = PasswordResetRequest.objects.filter(requested_by=user, is_resolved=True, notified=False)
            for req in resolved_requests:
                notes = f" Notes: {req.notes}" if req.notes else ''
                messages.info(request, f"Your password reset request from {req.requested_at:%b %d, %Y} has been resolved.{notes}")
                req.notified = True
                req.save()
            
            # Redirect students to enrollment if not completed
            if user.is_student and not user.is_enrollment_complete():
                return redirect('enrollment_start')
            return redirect('dashboard')
        else:
            # Login failed
            increment_failed_attempts(request, username)
            messages.error(request, 'Invalid email or password.')
    else:
        form = EnhancedLoginForm(request)

    return render(request, 'accounts/login.html', {'form': form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Set enrollment status to PENDING for new students
            if user.role == 'STUDENT':
                user.enrollment_status = 'PENDING'
                user.save()
                messages.success(request, 'Registration successful. Please complete your subject enrollment.')
                # Log the user in
                login(request, user, backend='accounts.backends.UsernameOrEmailBackend')
                return redirect('enrollment_start')
            else:
                messages.success(request, 'Registration successful. Please log in.')
                return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def logout_view(request):
    user = request.user
    logout(request)
    create_audit_log(user, 'LOGOUT', request)
    return redirect('login')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    instructors_count = User.objects.filter(role='INSTRUCTOR').count()
    students_count = User.objects.filter(role='STUDENT').count()
    subjects_count = Subject.objects.count()
    pending_password_requests = PasswordResetRequest.objects.filter(is_resolved=False).count()
    recent_requests = PasswordResetRequest.objects.filter(is_resolved=False).order_by('-requested_at')[:5]

    recent_activity = AuditLog.objects.filter(
        action__in=['USER_CREATE', 'USER_UPDATE', 'USER_DELETE', 'PASSWORD_CHANGE', 'LOGIN', 'LOGOUT']
    ).order_by('-timestamp')[:10]

    return render(request, 'accounts/admin_dashboard.html', {
        'instructors_count': instructors_count,
        'students_count': students_count,
        'subjects_count': subjects_count,
        'pending_password_requests': pending_password_requests,
        'recent_requests': recent_requests,
        'recent_activities': recent_activity,
        'current_time': timezone.now(),
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_user_list(request):
    users = User.objects.filter(role__in=['INSTRUCTOR', 'STUDENT']).order_by('-date_joined')
    return render(request, 'accounts/admin_users.html', {'users': users})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_instructor_list(request):
    instructors = User.objects.filter(role='INSTRUCTOR').order_by('-date_joined')
    return render(request, 'accounts/admin_instructors.html', {'instructors': instructors})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_student_list(request):
    students = User.objects.filter(role='STUDENT').order_by('-date_joined')
    return render(request, 'accounts/admin_students.html', {'students': students})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_create_instructor(request):
    if request.method == 'POST':
        form = AdminInstructorForm(request.POST)
        if form.is_valid():
            form.save()
            create_audit_log(request.user, 'USER_CREATE', request, {'target_user': form.cleaned_data.get('email')})
            messages.success(request, 'Instructor account successfully created.')
            return redirect('admin_instructor_list')
    else:
        form = AdminInstructorForm()
    return render(request, 'accounts/admin_create_instructor.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_edit_user(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    if user_obj.is_superuser:
        messages.error(request, 'Cannot modify superuser accounts here.')
        return redirect('admin_dashboard')

    if request.method == 'POST':
        form = AdminUserEditForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            create_audit_log(request.user, 'USER_UPDATE', request, {'target_user': user_obj.email})
            messages.success(request, 'Account details updated successfully.')
            return redirect('admin_user_list')
    else:
        form = AdminUserEditForm(instance=user_obj)
    return render(request, 'accounts/admin_edit_user.html', {'form': form, 'account': user_obj})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_delete_user(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    if user_obj.is_superuser:
        messages.error(request, 'Cannot delete superuser accounts.')
        return redirect('admin_dashboard')

    if request.method == 'POST':
        create_audit_log(request.user, 'USER_DELETE', request, {'target_user': user_obj.email})
        user_obj.delete()
        messages.success(request, 'Account deleted successfully.')
        return redirect('admin_dashboard')

    return render(request, 'accounts/admin_delete_user.html', {'account': user_obj})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_toggle_user_status(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    if user_obj.is_superuser:
        messages.error(request, 'Cannot change status of superuser accounts.')
    else:
        user_obj.is_active = not user_obj.is_active
        user_obj.save()
        messages.success(request, f"Account {'activated' if user_obj.is_active else 'deactivated'}.")
    return redirect('admin_dashboard')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_change_user_password(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    if user_obj.is_superuser:
        messages.error(request, 'Cannot reset superuser password here.')
        return redirect('admin_dashboard')

    if request.method == 'POST':
        form = AdminPasswordResetForm(request.POST)
        if form.is_valid():
            user_obj.set_password(form.cleaned_data['new_password'])
            user_obj.save()
            PasswordHistory.objects.create(user=user_obj, password_hash=user_obj.password)
            create_audit_log(request.user, 'PASSWORD_CHANGE', request, {'target_user': user_obj.email})
            messages.success(request, 'Password has been updated successfully.')
            return redirect('admin_dashboard')
    else:
        form = AdminPasswordResetForm()

    return render(request, 'accounts/admin_change_password.html', {'form': form, 'account': user_obj})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_password_requests(request):
    pending = PasswordResetRequest.objects.filter(is_resolved=False).order_by('-requested_at')
    resolved = PasswordResetRequest.objects.filter(is_resolved=True).order_by('-resolved_at')[:20]
    return render(request, 'accounts/admin_password_requests.html', {'pending_requests': pending, 'resolved_requests': resolved})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_resolve_password_request(request, request_id):
    request_obj = get_object_or_404(PasswordResetRequest, id=request_id)
    if request.method == 'POST':
        request_obj.is_resolved = True
        request_obj.resolved_by = request.user
        request_obj.resolved_at = timezone.now()
        request_obj.notes = request.POST.get('notes', '')
        request_obj.notified = False
        request_obj.save()
        create_audit_log(request.user, 'PASSWORD_CHANGE', request, {'resolved_request': request_obj.id})
        messages.success(request, 'Password reset request marked as resolved.')
    return redirect('admin_password_requests')


def password_reset_request(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            target_user = form.cleaned_data['username_or_email']
            PasswordResetRequest.objects.get_or_create(requested_by=target_user, is_resolved=False)
            messages.success(request, 'Password reset request sent to admin. Please wait for approval.')
            return redirect('login')
    else:
        form = PasswordResetRequestForm()
    return render(request, 'accounts/password_reset_request.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.role == 'INSTRUCTOR')
def instructor_subjects(request):
    subjects = Subject.objects.filter(instructor=request.user).order_by('code')
    today_name = date.today().strftime('%A')
    return render(request, 'dashboard/instructor_subjects.html', {
        'subjects': subjects,
        'today_name': today_name,
    })


@login_required
@user_passes_test(lambda u: u.role == 'INSTRUCTOR')
def instructor_edit_subject(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, instructor=request.user)
    from accounts.forms import InstructorSubjectForm

    if request.method == 'POST':
        form = InstructorSubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject details updated successfully.')
            return redirect('instructor_subjects')
    else:
        form = InstructorSubjectForm(instance=subject)

    return render(request, 'dashboard/instructor_edit_subject.html', {'form': form, 'subject': subject})


@login_required
@user_passes_test(lambda u: u.role == 'INSTRUCTOR')
def instructor_subject_attendance(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, instructor=request.user)
    records = AttendanceRecord.objects.filter(schedule__section__subject=subject)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        records = records.filter(date__gte=date_from)
    if date_to:
        records = records.filter(date__lte=date_to)

    summary = records.aggregate(
        present=Count(Case(When(status='PRESENT', then=1), output_field=IntegerField())),
        late=Count(Case(When(status='LATE', then=1), output_field=IntegerField())),
        absent=Count(Case(When(status='ABSENT', then=1), output_field=IntegerField())),
    )

    student_records = records.select_related('user', 'schedule').order_by('-date', 'user__last_name')[:200]
    attendance_by_date = records.values('date').annotate(
        present=Count(Case(When(status='PRESENT', then=1), output_field=IntegerField())),
        late=Count(Case(When(status='LATE', then=1), output_field=IntegerField())),
        absent=Count(Case(When(status='ABSENT', then=1), output_field=IntegerField())),
        total=Count('id')
    ).order_by('-date')

    return render(request, 'dashboard/instructor_subject_attendance.html', {
        'subject': subject,
        'summary': summary,
        'student_records': student_records,
        'attendance_by_date': attendance_by_date,
        'date_from': date_from,
        'date_to': date_to,
    })


@login_required
def enrollment_start(request):
    """First step: Select year level and section"""
    user = request.user
    
    # Only student accounts may access enrollment pages
    if user.is_superuser or user.is_staff or not user.is_student:
        messages.error(request, 'Only student accounts can enroll in subjects.')
        return redirect('dashboard')
    
    # If already enrolled, redirect to enrollment subjects page
    if user.year_level and user.section:
        return redirect('enrollment_subjects')
    
    if request.method == 'POST':
        year_level = request.POST.get('year_level')
        section = request.POST.get('section')
        
        if year_level and section:
            user.year_level = year_level
            user.section = section
            user.save()
            return redirect('enrollment_subjects')
        else:
            messages.error(request, 'Please select both year level and section.')
    
    context = {
        'year_choices': User.YEAR_LEVEL_CHOICES,
        'section_choices': User.SECTION_CHOICES,
    }
    return render(request, 'accounts/enrollment_start.html', context)


@login_required
def enrollment_subjects(request):
    """Second step: Select subjects to enroll in"""
    from accounts.models import Subject, StudentEnrollment
    
    user = request.user
    
    # Only student accounts may access enrollment pages
    if user.is_superuser or user.is_staff or not user.is_student:
        messages.error(request, 'Only student accounts can enroll in subjects.')
        return redirect('dashboard')
    
    # User must have selected year level and section first
    if not user.year_level or not user.section:
        return redirect('enrollment_start')
    
    # Get all subjects for this year and section
    required_subjects = Subject.objects.filter(
        year_level=user.year_level,
        section=user.section
    ).order_by('code')
    
    # Get already enrolled subjects
    enrolled_subject_ids = StudentEnrollment.objects.filter(
        student=user,
        is_active=True
    ).values_list('subject_id', flat=True)
    
    if request.method == 'POST':
        subject_ids = request.POST.getlist('subjects')
        
        # Remove old enrollments
        StudentEnrollment.objects.filter(student=user).delete()
        
        # Create new enrollments
        for subject_id in subject_ids:
            try:
                subject = Subject.objects.get(
                    id=subject_id,
                    year_level=user.year_level,
                    section=user.section
                )
                StudentEnrollment.objects.create(student=user, subject=subject)
            except Subject.DoesNotExist:
                pass
        
        # Update enrollment status
        user.update_enrollment_status()
        user.enrollment_completed_date = timezone.now()
        user.save()

        return redirect('dashboard')
    
    context = {
        'required_subjects': required_subjects,
        'enrolled_subject_ids': list(enrolled_subject_ids),
        'year_level': user.get_year_level_display(),
        'section': user.get_section_display(),
    }
    return render(request, 'accounts/enrollment_subjects.html', context)
