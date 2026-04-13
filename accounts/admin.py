from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.utils import timezone
from .models import CustomUser, AuditLog, PasswordHistory, PasswordResetRequest, Subject, StudentEnrollment


@admin.register(CustomUser)
class CustomUserAdmin(DefaultUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'year_level', 'section', 'enrollment_status', 'is_active')
    list_filter = ('role', 'enrollment_status', 'year_level', 'section', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'student_id', 'employee_id')
    ordering = ('-date_joined',)

    fieldsets = DefaultUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('role', 'student_id', 'employee_id', 'department', 'phone_number', 'is_enrolled')
        }),
        ('Enrollment', {
            'fields': ('year_level', 'section', 'enrollment_status', 'enrollment_completed_date'),
        }),
        ('Security', {
            'fields': ('login_attempts', 'lockout_until', 'last_login_ip'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = DefaultUserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('email', 'first_name', 'last_name', 'role', 'student_id', 'employee_id', 'department', 'phone_number')
        }),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'user__email', 'ip_address')
    readonly_fields = ('id', 'timestamp')
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('user', 'password_hash', 'created_at')


@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(admin.ModelAdmin):
    list_display = ('requested_by', 'requested_at', 'is_resolved', 'resolved_by', 'resolved_at')
    list_filter = ('is_resolved', 'requested_at', 'resolved_at')
    search_fields = ('requested_by__username', 'requested_by__email')
    readonly_fields = ('requested_by', 'requested_at', 'resolved_by', 'resolved_at')
    actions = ['mark_resolved']

    def mark_resolved(self, request, queryset):
        count = 0
        for item in queryset.filter(is_resolved=False):
            item.is_resolved = True
            item.resolved_by = request.user
            item.resolved_at = timezone.now()
            item.save()
            count += 1
        self.message_user(request, f"Marked {count} request(s) resolved.")

    mark_resolved.short_description = 'Mark selected requests resolved'


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'year_level', 'section', 'units')
    list_filter = ('year_level', 'section', 'created_at')
    search_fields = ('code', 'title', 'description')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('year_level', 'section', 'code')

    fieldsets = (
        ('Subject Information', {
            'fields': ('code', 'title', 'description')
        }),
        ('Program Details', {
            'fields': ('year_level', 'section', 'units')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StudentEnrollment)
class StudentEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'enrolled_date', 'is_active')
    list_filter = ('is_active', 'enrolled_date', 'subject__year_level', 'subject__section')
    search_fields = ('student__username', 'student__email', 'subject__code', 'subject__title')
    readonly_fields = ('enrolled_date',)
    ordering = ('-enrolled_date',)

    fieldsets = (
        ('Enrollment Information', {
            'fields': ('student', 'subject', 'is_active')
        }),
        ('Timestamp', {
            'fields': ('enrolled_date',),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
