from django.urls import path
from .api_views import (
    FaceEnrollmentView, FaceEncodingListView, EnrollmentRequestListView,
    approve_enrollment, reject_enrollment
)

app_name = 'faces_api'

urlpatterns = [
    path('enroll/', FaceEnrollmentView.as_view(), name='face_enrollment'),
    path('encodings/', FaceEncodingListView.as_view(), name='face_encodings'),
    path('enrollment-requests/', EnrollmentRequestListView.as_view(), name='enrollment_requests'),
    path('enrollment-requests/<int:request_id>/approve/', approve_enrollment, name='approve_enrollment'),
    path('enrollment-requests/<int:request_id>/reject/', reject_enrollment, name='reject_enrollment'),
]