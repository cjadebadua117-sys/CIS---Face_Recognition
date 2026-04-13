from rest_framework import generics, status, permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from geopy.distance import geodesic
from django.conf import settings
from .models import AttendanceRecord, Schedule, AttendanceAppeal, QRCode, AttendanceSession
from .tasks import send_attendance_notification
from accounts.models import AuditLog
from faces.models import FaceEncoding, Subject
try:
    import face_recognition
except Exception:
    face_recognition = None
import numpy as np
import base64
import io
from PIL import Image
import uuid


def normalize_subject_code(code):
    return ''.join(str(code).split()).upper() if code else ''


class ScheduleSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='section.subject.name', read_only=True)
    subject_code = serializers.CharField(source='section.subject.code', read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = [
            'id', 'subject', 'subject_name', 'subject_code', 'days_of_week',
            'start_time', 'end_time', 'room', 'grace_period_minutes',
            'auto_absent_minutes', 'is_active'
        ]

    def get_is_active(self, obj):
        return obj.is_active_now()


class AttendanceRecordSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    schedule_name = serializers.CharField(source='schedule.section.subject.name', read_only=True)
    subject_code = serializers.CharField(source='schedule.section.subject.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    duration_display = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'user', 'user_name', 'schedule', 'schedule_name', 'subject_code',
            'date', 'check_in_time', 'check_out_time', 'status', 'status_display',
            'latitude', 'longitude', 'is_within_geofence', 'confidence_score',
            'manually_marked', 'marked_by', 'duration_display', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_duration_display(self, obj):
        if obj.duration:
            hours, remainder = divmod(int(obj.duration), 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return None


class AttendanceCheckInView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        session_id = request.data.get('session_id')
        action = request.data.get('action', 'present')
        image_data = request.data.get('image')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')

        if action not in ['present', 'late']:
            return Response(
                {'error': 'Invalid attendance action'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not session_id:
            return Response(
                {'error': 'Session ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            session = AttendanceSession.objects.get(id=session_id)
        except AttendanceSession.DoesNotExist:
            return Response(
                {'error': 'Attendance session not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if session is open
        if not session.is_open:
            return Response(
                {'error': 'Attendance session is not currently open'},
                status=status.HTTP_400_BAD_REQUEST
            )

        schedule = session.schedule
        now = timezone.now()

        # Determine status based on session and action
        status_value = session.get_status_for_scan()
        if action == 'present':
            if status_value != 'PRESENT':
                return Response(
                    {'error': 'Present check-in is only allowed within the camera window.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not session.camera_enabled:
                return Response(
                    {'error': 'Camera attendance window has closed for this session.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not image_data:
                return Response(
                    {'error': 'Camera image is required for present check-in.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif action == 'late':
            if status_value != 'LATE':
                return Response(
                    {'error': 'Late check-in is only allowed during the late attendance window.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if status_value == 'ABSENT':
            return Response(
                {'error': 'Attendance window has closed. This session is marked absent.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check geofencing if coordinates provided
        is_within_geofence = True
        if latitude and longitude:
            campus_coords = (settings.NLUC_LATITUDE, settings.NLUC_LONGITUDE)
            user_coords = (float(latitude), float(longitude))
            distance = geodesic(campus_coords, user_coords).meters
            is_within_geofence = distance <= settings.GEOFENCE_RADIUS_METERS

            if not is_within_geofence:
                return Response(
                    {'error': 'You are outside the campus geofence'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Check if already checked in for this session
        existing_record = AttendanceRecord.objects.filter(
            user=user,
            schedule=schedule,
            date=session.date
        ).first()

        if existing_record and existing_record.check_in_time:
            return Response(
                {'error': 'Already checked in for this session today'},
                status=status.HTTP_400_BAD_REQUEST
            )

        confidence_score = None
        face_encoding_used = None

        # Face recognition verification if image provided
        if image_data:
            try:
                if face_recognition is None:
                    return Response(
                        {'error': 'Face recognition library is not installed.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                # Decode and process image
                image_data = image_data.split(',')[1] if ',' in image_data else image_data
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))

                if image.mode != 'RGB':
                    image = image.convert('RGB')

                image_array = np.array(image)

                # Detect and encode face
                face_locations = face_recognition.face_locations(image_array)
                if not face_locations:
                    return Response(
                        {'error': 'No face detected in the image. Please align your face with the camera.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if len(face_locations) > 1:
                    return Response(
                        {'error': 'Multiple faces detected. Please ensure only one person is visible.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                face_encodings = face_recognition.face_encodings(image_array, face_locations)
                if not face_encodings:
                    return Response(
                        {'error': 'Could not encode face. Please try again with better lighting.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                captured_encoding = face_encodings[0]

                # Compare with user's stored encodings
                user_encodings = FaceEncoding.objects.filter(
                    user=user,
                    is_active=True
                )

                if not user_encodings.exists():
                    return Response(
                        {'error': 'No face enrollment data found for this account.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                stored_encodings = [stored_encoding.encoding_array for stored_encoding in user_encodings]
                distances = face_recognition.face_distance(stored_encodings, captured_encoding)

                best_index = int(np.argmin(distances))
                best_distance = float(distances[best_index])
                best_match = user_encodings[best_index]

                if best_distance <= settings.FACE_RECOGNITION_THRESHOLD:
                    confidence_score = max(0.0, 1.0 - best_distance)
                    face_encoding_used = best_match
                else:
                    return Response(
                        {'error': 'Face not recognized. Please try again or contact the administrator.'},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
            except Exception as e:
                return Response(
                    {'error': f'Face recognition failed: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        now = timezone.now()

        # Determine status based on session
        status_value = session.get_status_for_scan()
        if status_value is None:
            return Response(
                {'error': 'Session is not open for attendance'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create or update attendance record
        if existing_record:
            existing_record.check_in_time = now
            existing_record.status = status_value
            existing_record.latitude = latitude
            existing_record.longitude = longitude
            existing_record.is_within_geofence = is_within_geofence
            existing_record.confidence_score = confidence_score
            existing_record.face_encoding_used = face_encoding_used
            existing_record.save()
            record = existing_record
        else:
            record = AttendanceRecord.objects.create(
                user=user,
                schedule=schedule,
                date=session.date,
                check_in_time=now,
                status=status_value,
                latitude=latitude,
                longitude=longitude,
                is_within_geofence=is_within_geofence,
                confidence_score=confidence_score,
                face_encoding_used=face_encoding_used
            )

        # Send notification
        send_attendance_notification.delay(
            user.email,
            schedule.section.subject.name,
            record.get_status_display(),
            now
        )

        # Log attendance
        AuditLog.objects.create(
            user=user,
            action='ATTENDANCE_MARK',
            ip_address=self.get_client_ip(request),
            details={
                'schedule': schedule.section.subject.code,
                'status': status_value,
                'method': 'face_recognition' if confidence_score else 'manual'
            }
        )

        return Response({
            'message': 'Check-in successful',
            'record': AttendanceRecordSerializer(record).data
        })

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class AttendanceCheckOutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        schedule_id = request.data.get('schedule_id')

        if not schedule_id:
            return Response(
                {'error': 'Schedule ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        now = timezone.now()

        try:
            record = AttendanceRecord.objects.get(
                user=user,
                schedule_id=schedule_id,
                date=now.date(),
                check_in_time__isnull=False,
                check_out_time__isnull=True
            )
        except AttendanceRecord.DoesNotExist:
            return Response(
                {'error': 'No active check-in found for this schedule'},
                status=status.HTTP_404_NOT_FOUND
            )

        record.check_out_time = now
        record.save()

        return Response({
            'message': 'Check-out successful',
            'record': AttendanceRecordSerializer(record).data
        })


class AttendanceRecordListView(generics.ListAPIView):
    serializer_class = AttendanceRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = AttendanceRecord.objects.select_related('user', 'schedule__section__subject')

        # Filter based on user role
        if user.is_student:
            queryset = queryset.filter(user=user)
        elif user.is_instructor:
            # Instructors can see attendance for their subjects
            queryset = queryset.filter(schedule__section__subject__instructor=user)
        # Admins can see all

        # Apply filters
        schedule_id = self.request.query_params.get('schedule')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        status_filter = self.request.query_params.get('status')

        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('-date', '-check_in_time')


class AttendanceAppealSerializer(serializers.ModelSerializer):
    attendance_details = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AttendanceAppeal
        fields = [
            'id', 'attendance_record', 'attendance_details', 'reason',
            'evidence', 'status', 'status_display', 'reviewed_by',
            'review_notes', 'submitted_at', 'reviewed_at'
        ]
        read_only_fields = ['id', 'submitted_at', 'reviewed_at']

    def get_attendance_details(self, obj):
        record = obj.attendance_record
        return {
            'subject': record.schedule.section.subject.name if record.schedule and record.schedule.section else None,
            'date': record.date,
            'status': record.get_status_display()
        }


class AttendanceAppealListView(generics.ListCreateAPIView):
    serializer_class = AttendanceAppealSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_student:
            return AttendanceAppeal.objects.filter(submitted_by=user)
        # Staff can see appeals for their subjects
        return AttendanceAppeal.objects.filter(
            attendance_record__schedule__section__subject__instructor=user
        )

    def perform_create(self, serializer):
        attendance_id = self.request.data.get('attendance_record')
        attendance_record = get_object_or_404(
            AttendanceRecord,
            id=attendance_id,
            user=self.request.user
        )

        # Check if appeal already exists
        if hasattr(attendance_record, 'appeal_details'):
            raise serializers.ValidationError("Appeal already submitted for this record")

        serializer.save(
            attendance_record=attendance_record,
            submitted_by=self.request.user
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def approve_appeal(request, appeal_id):
    user = request.user
    if not user.can_manage_users():
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )

    appeal = get_object_or_404(AttendanceAppeal, id=appeal_id)
    notes = request.data.get('notes', '')

    appeal.approve(user, notes)

    return Response({'message': 'Appeal approved'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def reject_appeal(request, appeal_id):
    user = request.user
    if not user.can_manage_users():
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )

    appeal = get_object_or_404(AttendanceAppeal, id=appeal_id)
    notes = request.data.get('notes', '')

    appeal.reject(user, notes)

    return Response({'message': 'Appeal rejected'})


class AttendanceSessionSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='schedule.section.subject.name', read_only=True)
    subject_code = serializers.CharField(source='schedule.section.subject.code', read_only=True)
    instructor_name = serializers.CharField(source='schedule.section.subject.instructor.get_full_name', read_only=True)
    countdown_info = serializers.SerializerMethodField()
    status_for_scan = serializers.SerializerMethodField()
    camera_enabled = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'schedule', 'date', 'is_open', 'opened_at', 'opened_by',
            'closed_at', 'closed_by', 'subject_name', 'subject_code',
            'instructor_name', 'grace_period_minutes', 'countdown_info',
            'status_for_scan', 'camera_enabled'
        ]

    def get_countdown_info(self, obj):
        return obj.get_countdown_info()

    def get_status_for_scan(self, obj):
        return obj.get_status_for_scan()

    def get_camera_enabled(self, obj):
        return obj.camera_enabled


class AttendanceSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get attendance sessions for today"""
        today = timezone.now().date()
        user = request.user

        if user.is_instructor:
            sessions = AttendanceSession.objects.filter(
                schedule__section__subject__instructor=user,
                date=today
            ).select_related('schedule__section__subject')
        else:
            enrolled_codes = [subject.code for subject in user.get_enrolled_subjects()]
            normalized_codes = list({normalize_subject_code(code) for code in enrolled_codes})
            sessions = AttendanceSession.objects.filter(
                schedule__section__subject__code__in=(enrolled_codes + normalized_codes),
                date=today
            ).select_related('schedule__section__subject')

        serializer = AttendanceSessionSerializer(sessions, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Open a new attendance session"""
        user = request.user
        schedule_id = request.data.get('schedule_id')

        if not user.is_instructor:
            return Response(
                {'error': 'Only instructors can open attendance sessions'},
                status=status.HTTP_403_FORBIDDEN
            )

        if not schedule_id:
            return Response(
                {'error': 'Schedule ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            schedule = Schedule.objects.get(id=schedule_id)
        except Schedule.DoesNotExist:
            return Response(
                {'error': 'Schedule not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if schedule.section.subject.instructor != user:
            return Response(
                {'error': 'You are not authorized to manage this schedule'},
                status=status.HTTP_403_FORBIDDEN
            )

        today = timezone.now().date()
        existing_session = AttendanceSession.objects.filter(
            schedule=schedule,
            date=today
        ).first()

        if existing_session:
            if existing_session.is_open:
                return Response(
                    {'error': 'Session is already open'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            existing_session.open_session(user)
            serializer = AttendanceSessionSerializer(existing_session)
            return Response(serializer.data)

        session = AttendanceSession.objects.create(
            schedule=schedule,
            date=today
        )
        session.open_session(user)

        serializer = AttendanceSessionSerializer(session)
        return Response(serializer.data)

    def patch(self, request, pk=None):
        """Close an attendance session"""
        user = request.user

        if not user.is_instructor:
            return Response(
                {'error': 'Only instructors can close attendance sessions'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            session = AttendanceSession.objects.get(id=pk)
        except AttendanceSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if session.schedule.section.subject.instructor != user:
            return Response(
                {'error': 'You are not authorized to manage this session'},
                status=status.HTTP_403_FORBIDDEN
            )

        if not session.is_open:
            return Response(
                {'error': 'Session is already closed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        session.close_session(user)
        serializer = AttendanceSessionSerializer(session)
        return Response(serializer.data)


class QRCodeSerializer(serializers.ModelSerializer):
    qr_url = serializers.SerializerMethodField()

    class Meta:
        model = QRCode
        fields = ['id', 'code', 'is_active', 'expires_at', 'qr_url']
        read_only_fields = ['id', 'code', 'qr_url']

    def get_qr_url(self, obj):
        # In production, this would generate actual QR code URL
        return f"/qr/{obj.code}/"


class QRCodeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get or create active QR code
        qr_code = QRCode.objects.filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now()
        ).first()

        if not qr_code:
            qr_code = QRCode.objects.create(user=user)

        serializer = QRCodeSerializer(qr_code)
        return Response(serializer.data)

    def post(self, request):
        """Refresh QR code"""
        user = request.user

        # Deactivate existing codes
        QRCode.objects.filter(user=user, is_active=True).update(is_active=False)

        # Create new code
        qr_code = QRCode.objects.create(user=user)

        serializer = QRCodeSerializer(qr_code)
        return Response(serializer.data)