# CIS - Face Recognition Attendance System

A Django-based attendance system that uses face recognition and webcam streaming to automate in-person attendance tracking.

## Project Structure

- `manage.py` – Django project launcher
- `cis_project/` – Django project settings and URL configuration
- `accounts/` – authentication, registration, and user roles
- `faces/` – face enrollment, person model, and face encoding storage
- `attendance/` – real-time recognition, attendance logging, and record views
- `dashboard/` – summary stats and attendance trend dashboard
- `reports/` – export attendance reports to CSV and PDF
- `templates/` – HTML templates for all app pages
- `static/` – CSS and JavaScript assets
- `media/` – uploaded face images and captured attendance snapshots

## Requirements

Install the Python packages:

```bash
pip install -r requirements.txt
```

## Installing `dlib` and `face_recognition`

### Windows

1. Install Visual Studio Build Tools with C++ support.
2. Install CMake.
3. Activate your virtual environment, then run:

```bash
python -m pip install --upgrade pip
python -m pip install dlib face_recognition face_recognition_models
```

> If you use `pip install -r requirements.txt`, the `dlib` dependency is now included so the project installs cleanly.

### Linux

```bash
sudo apt update
sudo apt install build-essential cmake libgtk-3-dev libboost-python-dev
python3 -m pip install dlib face_recognition face_recognition_models
```

### macOS

```bash
brew install cmake
python3 -m pip install dlib face_recognition face_recognition_models
```

## Database Setup

Run migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

Create a superuser:

```bash
python manage.py createsuperuser
```

## Run the Development Server

```bash
python manage.py runserver
```

Open the app at `http://127.0.0.1:8000/`.

## Access the Webcam

The face enrollment page uses browser media access to capture webcam frames. When prompted, allow camera access in the browser.

## URLs

- `/` → Dashboard if logged in, otherwise login
- `/login/` → Login page
- `/register/` → User registration
- `/logout/` → Logout
- `/dashboard/` → Main dashboard
- `/faces/` → Face enrollment list
- `/faces/enroll/` → Enroll new face
- `/faces/<id>/delete/` → Delete enrolled person
- `/attendance/start/` → Live recognition page
- `/attendance/stream/` → MJPEG video stream
- `/attendance/records/` → Attendance record list
- `/reports/export/csv/` → Download filtered attendance as CSV
- `/reports/export/pdf/` → Download filtered attendance as PDF

## Notes

- Only admin users can enroll new faces and manage users.
- The live attendance stream uses OpenCV to detect faces and compare against stored encodings.
- Attendance is prevented from duplicate logging for the same person on the same day.
