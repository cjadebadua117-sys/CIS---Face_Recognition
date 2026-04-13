from django.urls import path
from attendance import views

urlpatterns = [
    path('start/', views.attendance_start, name='attendance_start'),
    path('stream/', views.attendance_stream, name='attendance_stream'),
    path('records/', views.attendance_records, name='attendance_records'),
]
