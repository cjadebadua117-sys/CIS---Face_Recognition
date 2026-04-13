from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from .models import AuditLog
from .serializers import (
    UserSerializer, UserRegistrationSerializer, UserProfileSerializer,
    ChangePasswordSerializer, AuditLogSerializer
)


class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Log registration
        AuditLog.objects.create(
            user=user,
            action='USER_CREATE',
            ip_address=self.get_client_ip(request),
            details={'registered_by': 'self'}
        )

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @ratelimit(key='ip', rate='5/m', block=True)
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(request, username=email, password=password)

        if user is None:
            # Log failed login attempt
            AuditLog.objects.create(
                action='LOGIN_FAILED',
                ip_address=self.get_client_ip(request),
                details={'email': email}
            )
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Check if user is locked out
        if user.is_locked_out():
            return Response(
                {'error': 'Account is temporarily locked due to too many failed attempts'},
                status=status.HTTP_423_LOCKED
            )

        # Reset login attempts on successful login
        user.reset_login_attempts()

        # Log successful login
        AuditLog.objects.create(
            user=user,
            action='LOGIN',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        # Verify old password
        if not user.check_password(serializer.validated_data['old_password']):
            AuditLog.objects.create(
                user=user,
                action='PASSWORD_CHANGE',
                ip_address=self.get_client_ip(request),
                details={'result': 'failed', 'reason': 'wrong_old_password'}
            )
            return Response(
                {'error': 'Current password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Change password
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        # Log password change
        AuditLog.objects.create(
            user=user,
            action='PASSWORD_CHANGE',
            ip_address=self.get_client_ip(request),
            details={'result': 'success'}
        )

        return Response({'message': 'Password changed successfully'})

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_system_admin or user.is_registrar:
            # Admins can see all logs
            return AuditLog.objects.all()
        else:
            # Regular users can only see their own logs
            return AuditLog.objects.filter(user=user)

    def get(self, request, *args, **kwargs):
        # Log audit log access
        AuditLog.objects.create(
            user=request.user,
            action='USER_UPDATE',
            ip_address=self.get_client_ip(request),
            details={'accessed': 'audit_logs'}
        )
        return super().get(request, *args, **kwargs)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    try:
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()

        # Log logout
        AuditLog.objects.create(
            user=request.user,
            action='LOGOUT',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        return Response({'message': 'Successfully logged out'})
    except Exception as e:
        return Response(
            {'error': 'Invalid token'},
            status=status.HTTP_400_BAD_REQUEST
        )