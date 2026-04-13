from django.contrib import admin
from .models import Schedule, AttendanceRecord, AttendanceAppeal, QRCode


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['section', 'day_of_week', 'start_time', 'end_time', 'room']
    list_filter = ['section__subject__instructor', 'day_of_week']
    search_fields = ['section__subject__name', 'section__subject__code', 'room']

    def days_of_week_display(self, obj):
        return obj.get_day_of_week_display()
    days_of_week_display.short_description = 'Day'


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'schedule', 'date', 'check_in_time', 'status',
        'confidence_score', 'is_within_geofence', 'manually_marked'
    ]
    list_filter = ['status', 'date', 'is_within_geofence', 'manually_marked', 'schedule__section__subject__instructor']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name', 'schedule__section__subject__code']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'date'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'schedule', 'schedule__section__subject', 'marked_by'
        )


@admin.register(AttendanceAppeal)
class AttendanceAppealAdmin(admin.ModelAdmin):
    list_display = ['attendance_record', 'submitted_by', 'status', 'submitted_at', 'reviewed_at']
    list_filter = ['status', 'submitted_at', 'reviewed_at']
    search_fields = ['submitted_by__username', 'attendance_record__user__username']
    readonly_fields = ['submitted_at', 'reviewed_at']

    actions = ['approve_appeals', 'reject_appeals']

    def approve_appeals(self, request, queryset):
        for appeal in queryset.filter(status='PENDING'):
            appeal.approve(request.user, "Approved via admin")
        self.message_user(request, f"Approved {queryset.filter(status='APPROVED').count()} appeals.")

    def reject_appeals(self, request, queryset):
        for appeal in queryset.filter(status='PENDING'):
            appeal.reject(request.user, "Rejected via admin")
        self.message_user(request, f"Rejected {queryset.filter(status='REJECTED').count()} appeals.")

    approve_appeals.short_description = "Approve selected appeals"
    reject_appeals.short_description = "Reject selected appeals"


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ['user', 'code', 'is_active', 'expires_at', 'created_at']
    list_filter = ['is_active', 'created_at', 'expires_at']
    search_fields = ['user__username', 'user__email', 'code']
    readonly_fields = ['code', 'created_at']

    def has_add_permission(self, request):
        return False  # QR codes should be generated through the API
