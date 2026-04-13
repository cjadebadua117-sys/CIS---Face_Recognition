from django.urls import path
from .api_views import (
    RegisterView, LoginView, ProfileView, ChangePasswordView,
    AuditLogListView, logout_view
)

app_name = 'accounts_api'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('audit-logs/', AuditLogListView.as_view(), name='audit_logs'),
]