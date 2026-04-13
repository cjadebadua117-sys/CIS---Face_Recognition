from django.urls import path
from accounts import views
from dashboard import views as dashboard_views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/', views.password_reset_request, name='password_reset_request'),
    path('enrollment/start/', views.enrollment_start, name='enrollment_start'),
    path('enrollment/subjects/', views.enrollment_subjects, name='enrollment_subjects'),

    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/instructors/', views.admin_instructor_list, name='admin_instructor_list'),
    path('admin-panel/instructors/create/', views.admin_create_instructor, name='admin_create_instructor'),
    path('admin-panel/users/', views.admin_user_list, name='admin_user_list'),
    path('admin-panel/users/<int:user_id>/edit/', views.admin_edit_user, name='admin_edit_user'),
    path('admin-panel/users/<int:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),
    path('admin-panel/users/<int:user_id>/password/', views.admin_change_user_password, name='admin_change_user_password'),
    path('admin-panel/users/<int:user_id>/toggle-active/', views.admin_toggle_user_status, name='admin_toggle_user_status'),
    path('admin-panel/students/', views.admin_student_list, name='admin_student_list'),
    path('admin-panel/password-requests/', views.admin_password_requests, name='admin_password_requests'),
    path('admin-panel/password-requests/<int:request_id>/resolve/', views.admin_resolve_password_request, name='admin_resolve_password_request'),

    path('instructor/subjects/', dashboard_views.instructor_subjects, name='instructor_subjects'),
    path('instructor/subjects/add/', dashboard_views.add_subject, name='add_subject'),
    path('instructor/subjects/<int:subject_id>/edit/', dashboard_views.edit_subject, name='edit_subject'),
    path('instructor/subjects/<int:subject_id>/archive/', dashboard_views.archive_subject, name='archive_subject'),
    path('instructor/subjects/<int:subject_id>/sections/add/', dashboard_views.add_section, name='add_section'),
    path('instructor/subjects/<int:subject_id>/sections/<int:section_id>/open-attendance/', dashboard_views.open_section_attendance, name='open_section_attendance'),
    path('instructor/subjects/<int:subject_id>/sections/<int:section_id>/attendance/', dashboard_views.section_attendance, name='section_attendance'),
]
