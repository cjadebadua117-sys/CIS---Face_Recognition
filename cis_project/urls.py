from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='login', permanent=False), name='root'),
    path('admin/', admin.site.urls),

    # API endpoints
    path('api/', include([
        path('accounts/', include('accounts.api_urls')),
        path('faces/', include('faces.api_urls')),
        path('attendance/', include('attendance.api_urls')),
        path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
        path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    ])),

    # Web interface
    path('', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('faces/', include('faces.urls')),
    path('attendance/', include('attendance.urls')),
    path('reports/', include('reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
