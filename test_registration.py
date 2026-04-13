#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cis_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from accounts.forms import UserRegistrationForm

def test_registration():
    """Test user registration functionality"""
    client = Client()

    # Test data
    test_data = {
        'username': 'testuser123',
        'student_id': 'STU001',
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'password1': 'testpass123!',
        'password2': 'testpass123!',
    }

    print("Testing user registration...")

    # Submit registration form
    response = client.post('/register/', test_data)

    if response.status_code == 302:  # Redirect after successful registration
        print("✓ Registration successful - redirect to dashboard")

        # Check if user was created
        User = get_user_model()
        try:
            user = User.objects.get(username='testuser123')
            print(f"✓ User created: {user.username} ({user.email})")

            # Check if user is logged in
            if '_auth_user_id' in client.session:
                print("✓ User is logged in after registration")
            else:
                print("✗ User not logged in after registration")

        except User.DoesNotExist:
            print("✗ User was not created")

    elif response.status_code == 200:
        # Form had errors
        form = UserRegistrationForm(test_data)
        if not form.is_valid():
            print("✗ Form validation errors:")
            for field, errors in form.errors.items():
                print(f"  {field}: {', '.join(errors)}")
        else:
            print("✗ Unexpected 200 response - form should redirect on success")

    else:
        print(f"✗ Unexpected response status: {response.status_code}")
        print(f"Response content: {response.content.decode()[:500]}...")

if __name__ == '__main__':
    test_registration()