from django.contrib import admin
from .models import AttendanceReport, SystemHealthLog, NotificationLog


@admin.register(AttendanceReport)
class AttendanceReportAdmin(admin.ModelAdmin):
    list_display = ['schedule', 'report_type', 'generated_by', 'generated_at', 'date_from', 'date_to']
    list_filter = ['report_type', 'generated_at', 'schedule__section__subject__instructor']
    search_fields = ['schedule__section__subject__name', 'schedule__section__subject__code']
    readonly_fields = ['generated_at', 'data']

    def has_add_permission(self, request):
        return False  # Reports should be generated through tasks/views


@admin.register(SystemHealthLog)
class SystemHealthLogAdmin(admin.ModelAdmin):
    list_display = ['component', 'status', 'timestamp', 'message']
    list_filter = ['component', 'status', 'timestamp']
    search_fields = ['component', 'message']
    readonly_fields = ['timestamp', 'metrics']

    def has_add_permission(self, request):
        return False  # Health logs should be created by monitoring systems

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'subject', 'sent_at', 'delivered']
    list_filter = ['notification_type', 'delivered', 'sent_at']
    search_fields = ['user__username', 'user__email', 'subject']
    readonly_fields = ['sent_at']

    def has_add_permission(self, request):
        return False  # Notification logs should be created by the notification system