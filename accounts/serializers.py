from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import AuditLog

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'role_display', 'student_id', 'employee_id', 'department',
            'phone_number', 'is_enrolled', 'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']

    def get_full_name(self, obj):
        return obj.get_full_name()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=12)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'role', 'student_id', 'employee_id',
            'department', 'phone_number'
        ]

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords do not match")

        if data.get('role') == 'STUDENT' and not data.get('student_id'):
            raise serializers.ValidationError("Student ID is required for students")

        if data.get('role') in ['INSTRUCTOR', 'DEPARTMENT_HEAD', 'REGISTRAR'] and not data.get('employee_id'):
            raise serializers.ValidationError("Employee ID is required for staff")

        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'student_id', 'employee_id', 'department',
            'phone_number', 'is_enrolled'
        ]
        read_only_fields = ['id', 'username', 'email', 'role', 'is_enrolled']


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=12)
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError("New passwords do not match")
        return data


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'action', 'action_display',
            'ip_address', 'user_agent', 'details', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']