from django.contrib import admin
from .models import Department, Subject, Section, FaceEncoding, EnrollmentRequest


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'head']
    search_fields = ['name', 'code']
    list_filter = ['head']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'instructor', 'semester', 'school_year', 'is_archived']
    search_fields = ['name', 'code', 'instructor__username', 'instructor__email']
    list_filter = ['semester', 'school_year', 'is_archived', 'instructor']


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ['subject', 'name', 'schedule_day', 'schedule_time', 'room']
    search_fields = ['subject__name', 'subject__code', 'name']
    list_filter = ['schedule_day', 'subject__semester', 'subject__school_year']


@admin.register(FaceEncoding)
class FaceEncodingAdmin(admin.ModelAdmin):
    list_display = ['user', 'angle', 'quality_score', 'is_liveness_verified', 'is_active', 'created_at']
    list_filter = ['angle', 'is_liveness_verified', 'is_active', 'created_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['encoding']  # Don't show binary data in admin

    def has_add_permission(self, request):
        return False  # Face encodings should be created through the enrollment process


@admin.register(EnrollmentRequest)
class EnrollmentRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'submitted_at', 'reviewed_at', 'reviewed_by']
    list_filter = ['status', 'submitted_at', 'reviewed_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['submitted_at', 'reviewed_at']

    actions = ['approve_requests', 'reject_requests']

    def approve_requests(self, request, queryset):
        for enrollment_request in queryset.filter(status='PENDING'):
            enrollment_request.approve(request.user)
        self.message_user(request, f"Approved {queryset.filter(status='APPROVED').count()} enrollment requests.")

    def reject_requests(self, request, queryset):
        for enrollment_request in queryset.filter(status='PENDING'):
            enrollment_request.reject(request.user, "Bulk rejection")
        self.message_user(request, f"Rejected {queryset.filter(status='REJECTED').count()} enrollment requests.")

    approve_requests.short_description = "Approve selected enrollment requests"
    reject_requests.short_description = "Reject selected enrollment requests"
