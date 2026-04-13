import base64
import io
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render
from PIL import Image
import numpy as np
from .forms import PersonEnrollmentForm
from .models import FaceEncoding
from django.contrib.auth import get_user_model

try:
    import face_recognition
except Exception:
    face_recognition = None

User = get_user_model()


def is_admin_user(user):
    return user.is_superuser or getattr(user, 'is_staff', False)


def detect_face_encoding(image):
    """Detect and encode the main face in the image."""
    image = image.convert('RGB')
    image_array = np.array(image)

    if not face_recognition:
        raise RuntimeError('Face recognition library is not available. Please install the face_recognition package.')

    face_locations = face_recognition.face_locations(image_array)
    if not face_locations:
        raise ValueError('No face detected in image')
    if len(face_locations) > 1:
        raise ValueError('Multiple faces detected. Please ensure only one face is visible.')

    face_encodings = face_recognition.face_encodings(image_array, face_locations)
    if not face_encodings:
        raise ValueError('Could not encode face. Please try again.')

    return face_encodings[0]


def calculate_quality_score(image, face_box=None):
    """Return a simple quality score based on face area and clarity."""
    if face_box is None:
        return 0.7
    top, right, bottom, left = face_box
    face_area = max(1, (right - left) * (bottom - top))
    image_area = image.width * image.height
    return min(1.0, max(0.3, face_area / image_area * 4.0))


def faces_list(request):
    """Face enrollment view with form submission"""
    if not request.user.is_authenticated:
        return redirect('login')

    form = PersonEnrollmentForm()
    persons = []
    if request.user.is_system_admin or request.user.is_registrar:
        persons = User.objects.filter(face_encodings__is_active=True).distinct().order_by('-face_encodings__created_at')[:12]
    else:
        persons = [request.user] if FaceEncoding.objects.filter(user=request.user, is_active=True).exists() else []

    if request.method == 'POST':
        form = PersonEnrollmentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                if request.user.is_system_admin or request.user.is_registrar:
                    name = form.cleaned_data.get('name', '')
                    person_id = form.cleaned_data.get('person_id', '')
                    if not person_id:
                        messages.error(request, 'Person ID is required.')
                        return render(request, 'faces/enroll.html', {'form': form, 'persons': persons})

                    try:
                        target_user = User.objects.get(username=person_id)
                    except User.DoesNotExist:
                        target_user = User.objects.create_user(
                            username=person_id,
                            email=f'{person_id}@system.local',
                            first_name=name.split()[0] if name else person_id,
                            last_name=' '.join(name.split()[1:]) if ' ' in name else '',
                        )
                else:
                    target_user = request.user
                    name = f"{target_user.first_name} {target_user.last_name}".strip() or target_user.username
                    person_id = target_user.username

                photos_saved = 0
                angle_map = {1: 'FRONT', 2: 'LEFT', 3: 'RIGHT', 4: 'UP', 5: 'DOWN'}

                for i in range(1, 6):
                    photo_key = f'photoField{i}'
                    if photo_key in request.POST and request.POST[photo_key]:
                        photo_data = request.POST[photo_key]
                        try:
                            if photo_data.startswith('data:image'):
                                header, data = photo_data.split(',', 1)
                                image_data = base64.b64decode(data)
                                image = Image.open(io.BytesIO(image_data))
                                if image.mode != 'RGB':
                                    image = image.convert('RGB')

                                encoding = detect_face_encoding(image)
                                encoding_bytes = encoding.astype(np.float64).tobytes()

                                face_locations = None
                                if face_recognition:
                                    image_array = np.array(image)
                                    boxes = face_recognition.face_locations(image_array)
                                    face_locations = boxes[0] if boxes else None

                                angle = angle_map.get(i, 'FRONT')
                                quality_score = calculate_quality_score(image, face_locations)

                                FaceEncoding.objects.update_or_create(
                                    user=target_user,
                                    angle=angle,
                                    defaults={
                                        'encoding': encoding_bytes,
                                        'quality_score': quality_score,
                                        'is_liveness_verified': False
                                    }
                                )
                                photos_saved += 1
                        except Exception as e:
                            print(f'Error processing photo {i}: {str(e)}')
                            continue

                if photos_saved > 0:
                    if target_user == request.user and photos_saved >= 3:
                        request.user.is_enrolled = True
                        request.user.save()

                    messages.success(request, f'Face enrollment successful! Saved {photos_saved} face encoding(s).')
                    return redirect('faces_list')
                else:
                    messages.error(request, 'No photos were captured. Please capture at least 3 clear photos.')

            except Exception as e:
                print(f'Face enrollment error: {str(e)}')
                messages.error(request, f'Error saving face enrollment: {str(e)}')
                return render(request, 'faces/enroll.html', {'form': form, 'persons': persons})

    return render(request, 'faces/enroll.html', {'form': form, 'persons': persons})


@login_required
def enroll_person(request):
    """Redirect to faces_list for enrollment"""
    return redirect('faces_list')


@login_required
@user_passes_test(is_admin_user)
def delete_person(request, person_id):
    """Delete face encodings for a person"""
    try:
        # Try to find by person_id (username)
        user = User.objects.get(username=person_id)
        FaceEncoding.objects.filter(user=user).delete()
        messages.success(request, f'Face encodings for {user.get_full_name()} have been deleted.')
    except User.DoesNotExist:
        messages.error(request, 'Person not found.')
    
    return redirect('faces_list')
