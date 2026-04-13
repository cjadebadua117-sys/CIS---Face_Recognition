#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cis_project.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Set admin as student
admin = User.objects.filter(username='admin').first()
if admin:
    admin.role = 'STUDENT'
    admin.save()
    print(f"✓ Set admin user as STUDENT")

# Create an instructor account
if not User.objects.filter(username='instructor').exists():
    instructor = User.objects.create_user(
        username='instructor',
        email='instructor@dmmmsu.edu',
        password='Instructor@123456',
        first_name='John',
        last_name='Smith',
        role='INSTRUCTOR'
    )
    print(f"✓ Created instructor user: instructor / Instructor@123456")
else:
    print(f"✓ Instructor user already exists")

# Create a student account
if not User.objects.filter(username='student').exists():
    student = User.objects.create_user(
        username='student',
        email='student@dmmmsu.edu',
        password='Student@123456',
        first_name='Jane',
        last_name='Doe',
        role='STUDENT'
    )
    print(f"✓ Created student user: student / Student@123456")
else:
    print(f"✓ Student user already exists")

# Populate missing full names for existing students
updated_students = 0
for student in User.objects.filter(role='STUDENT'):
    if not student.first_name or not student.last_name:
        username = student.username or 'student'
        name_parts = username.replace('_', ' ').replace('.', ' ').split()
        if name_parts:
            student.first_name = name_parts[0].title()
            if len(name_parts) > 1:
                student.last_name = ' '.join(part.title() for part in name_parts[1:])
            else:
                student.last_name = 'Student'
        else:
            student.first_name = 'Student'
            student.last_name = 'User'
        student.save()
        updated_students += 1
        print(f"✓ Updated student full name for: {student.username} -> {student.first_name} {student.last_name}")

if updated_students == 0:
    print("✓ No existing student names needed updating")
