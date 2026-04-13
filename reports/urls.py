from django.urls import path
from reports import views

urlpatterns = [
    path('export/csv/', views.export_attendance_csv, name='report_export_csv'),
    path('export/pdf/', views.export_attendance_pdf, name='report_export_pdf'),
]
