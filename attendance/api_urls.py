from django.urls import path
from .api_views import (
    AttendanceCheckInView, AttendanceCheckOutView, AttendanceRecordListView,
    AttendanceAppealListView, approve_appeal, reject_appeal, QRCodeView,
    AttendanceSessionView
)

app_name = 'attendance_api'

urlpatterns = [
    path('check-in/', AttendanceCheckInView.as_view(), name='check_in'),
    path('check-out/', AttendanceCheckOutView.as_view(), name='check_out'),
    path('records/', AttendanceRecordListView.as_view(), name='records'),
    path('appeals/', AttendanceAppealListView.as_view(), name='appeals'),
    path('appeals/<int:appeal_id>/approve/', approve_appeal, name='approve_appeal'),
    path('appeals/<int:appeal_id>/reject/', reject_appeal, name='reject_appeal'),
    path('qr-code/', QRCodeView.as_view(), name='qr_code'),
    path('sessions/', AttendanceSessionView.as_view(), name='sessions'),
    path('sessions/<int:pk>/', AttendanceSessionView.as_view(), name='session_detail'),
]