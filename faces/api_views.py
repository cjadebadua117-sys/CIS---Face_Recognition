from rest_framework import generics, status, permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import FaceEncoding, EnrollmentRequest, Department, Subject
from accounts.models import AuditLog
try:
    import face_recognition
except Exception:
    face_recognition = None
import numpy as np
import base64
import io
from PIL import Image


class FaceEncodingSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = FaceEncoding
        fields = [
            'id', 'user', 'user_name', 'angle', 'quality_score',
            'is_liveness_verified', 'liveness_method', 'created_at',
            'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EnrollmentRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = EnrollmentRequest
        fields = [
            'id', 'user', 'user_name', 'status', 'status_display',
            'submitted_at', 'reviewed_at', 'reviewed_by', 'rejection_reason'
        ]
        read_only_fields = ['id', 'submitted_at', 'reviewed_at']


class FaceEnrollmentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        if not user.can_enroll_faces():
            return Response(
                {'error': 'You do not have permission to enroll faces'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if user already has face encodings
        existing_encodings = FaceEncoding.objects.filter(user=user, is_active=True)
        if existing_encodings.count() >= 5:  # Max 5 angles
            return Response(
                {'error': 'Maximum face encodings reached'},
                status=status.HTTP_400_BAD_REQUEST
            )

        image_data = request.data.get('image')
        angle = request.data.get('angle', 'FRONT')

        if not image_data:
            return Response(
                {'error': 'Image data is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Decode base64 image
            image_data = image_data.split(',')[1] if ',' in image_data else image_data
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Convert to numpy array
            image_array = np.array(image)

            if face_recognition is None:
                return Response(
                    {'error': 'Face recognition library is not installed.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Detect faces
            face_locations = face_recognition.face_locations(image_array)
            if not face_locations:
                return Response(
                    {'error': 'No face detected in image'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if len(face_locations) > 1:
                return Response(
                    {'error': 'Multiple faces detected. Please ensure only one face is visible'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get face encoding
            face_encodings = face_recognition.face_encodings(image_array, face_locations)
            if not face_encodings:
                return Response(
                    {'error': 'Could not encode face. Please try again'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            encoding = face_encodings[0]

            # Calculate quality score (simplified)
            # In production, this would use more sophisticated quality metrics
            quality_score = min(1.0, len(face_locations[0]) / 1000.0)  # Rough proxy

            if quality_score < 0.5:
                return Response(
                    {'error': 'Image quality too low. Please ensure good lighting and clear face'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check for liveness (simplified - in production use proper liveness detection)
            is_liveness_verified = request.data.get('liveness_verified', False)
            liveness_method = request.data.get('liveness_method', '')

            # Convert encoding to binary
            encoding_binary = encoding.tobytes()

            # Create face encoding record
            face_encoding = FaceEncoding.objects.create(
                user=user,
                encoding=encoding_binary,
                angle=angle,
                quality_score=quality_score,
                is_liveness_verified=is_liveness_verified,
                liveness_method=liveness_method
            )

            # Log enrollment
            AuditLog.objects.create(
                user=user,
                action='FACE_ENROLLMENT',
                ip_address=self.get_client_ip(request),
                details={
                    'angle': angle,
                    'quality_score': quality_score,
                    'liveness_verified': is_liveness_verified
                }
            )

            # Check if user has minimum required encodings for enrollment
            active_encodings = FaceEncoding.objects.filter(user=user, is_active=True)
            if active_encodings.count() >= 3 and not user.is_enrolled:
                user.is_enrolled = True
                user.save()

            return Response({
                'message': 'Face encoding saved successfully',
                'encoding_id': face_encoding.id,
                'quality_score': quality_score,
                'is_enrolled': user.is_enrolled
            })

        except Exception as e:
            return Response(
                {'error': f'Face processing failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class FaceEncodingListView(generics.ListAPIView):
    serializer_class = FaceEncodingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_system_admin or user.is_registrar:
            return FaceEncoding.objects.all()
        else:
            return FaceEncoding.objects.filter(user=user)


class EnrollmentRequestListView(generics.ListCreateAPIView):
    serializer_class = EnrollmentRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_system_admin or user.is_registrar:
            return EnrollmentRequest.objects.all()
        else:
            return EnrollmentRequest.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def approve_enrollment(request, request_id):
    user = request.user
    if not (user.is_system_admin or user.is_registrar):
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )

    enrollment_request = get_object_or_404(EnrollmentRequest, id=request_id)
    enrollment_request.approve(user)

    AuditLog.objects.create(
        user=user,
        action='USER_UPDATE',
        ip_address=request.META.get('REMOTE_ADDR'),
        details={'action': 'approved_enrollment', 'target_user': enrollment_request.user.id}
    )

    return Response({'message': 'Enrollment approved successfully'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def reject_enrollment(request, request_id):
    user = request.user
    if not (user.is_system_admin or user.is_registrar):
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )

    reason = request.data.get('reason', '')
    enrollment_request = get_object_or_404(EnrollmentRequest, id=request_id)
    enrollment_request.reject(user, reason)

    AuditLog.objects.create(
        user=user,
        action='USER_UPDATE',
        ip_address=request.META.get('REMOTE_ADDR'),
        details={'action': 'rejected_enrollment', 'target_user': enrollment_request.user.id, 'reason': reason}
    )

    return Response({'message': 'Enrollment rejected'})


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'head']


class SubjectSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    instructor_name = serializers.CharField(source='instructor.get_full_name', read_only=True)

    class Meta:
        model = Subject
        fields = [
            'id', 'name', 'code', 'department', 'department_name',
            'instructor', 'instructor_name', 'semester', 'academic_year'
        ]