from django.urls import path
from dashboard import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('instructor/', views.instructor_dashboard, name='instructor_dashboard'),
    path('instructor/subjects/', views.instructor_subjects, name='instructor_subjects'),
    path('instructor/subjects/add/', views.add_subject, name='add_subject'),
    path('instructor/subjects/<int:subject_id>/edit/', views.edit_subject, name='edit_subject'),
    path('instructor/subjects/<int:subject_id>/archive/', views.archive_subject, name='archive_subject'),
    path('instructor/subjects/<int:subject_id>/delete/', views.delete_subject, name='delete_subject'),
    path('instructor/subjects/<int:subject_id>/sections/add/', views.add_section, name='add_section'),
    path('instructor/subjects/<int:subject_id>/sections/<int:section_id>/edit/', views.edit_section, name='edit_section'),
    path('instructor/subjects/<int:subject_id>/sections/<int:section_id>/delete/', views.delete_section, name='delete_section'),
    path('instructor/subjects/<int:subject_id>/sections/<int:section_id>/open-attendance/', views.open_section_attendance, name='open_section_attendance'),
    path('instructor/subjects/<int:subject_id>/sections/<int:section_id>/attendance/', views.section_attendance, name='section_attendance'),
]
