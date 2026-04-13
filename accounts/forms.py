from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from .models import CustomUser
from faces.models import Subject as FaceSubject


class EnhancedLoginForm(AuthenticationForm):
    """Enhanced login form with Remember Me and security features"""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address or username',
            'autocomplete': 'email',
            'autofocus': True,
            'id': 'id_username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
            'autocomplete': 'current-password',
            'id': 'id_password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_remember_me'
        }),
        label='Remember me'
    )

    def clean(self):
        """Enhanced validation with username/email support"""
        cleaned_data = self.cleaned_data
        username = cleaned_data.get('username')

        if username:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            if '@' in username:
                try:
                    user = User.objects.get(email__iexact=username)
                    cleaned_data['username'] = user.email or username
                except User.DoesNotExist:
                    try:
                        user = User.objects.get(username__iexact=username)
                        cleaned_data['username'] = user.email or username
                    except User.DoesNotExist:
                        cleaned_data['username'] = username
            else:
                try:
                    user = User.objects.get(username__iexact=username)
                    cleaned_data['username'] = user.username
                except User.DoesNotExist:
                    try:
                        user = User.objects.get(email__iexact=username)
                        cleaned_data['username'] = user.email or username
                    except User.DoesNotExist:
                        cleaned_data['username'] = username

        return super().clean()


class LoginForm(EnhancedLoginForm):
    """Backward compatible alias for EnhancedLoginForm"""
    pass


class UserRegistrationForm(UserCreationForm):
    """Simplified registration form for students only"""
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )
    student_id = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Student ID'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Gmail'
        })
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'student_id', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add form-control class to all fields
        for field_name in ['username', 'first_name', 'last_name', 'student_id', 'email', 'password1', 'password2']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'class': 'form-control'
                })
        # Set custom placeholders
        self.fields['username'].widget.attrs['placeholder'] = 'Username'
        self.fields['password1'].widget.attrs['placeholder'] = 'Password'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirm Password'
        
        # Remove help text from all fields
        self.fields['username'].help_text = ''
        self.fields['password1'].help_text = ''
        self.fields['password2'].help_text = ''

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'STUDENT'  # Force student role for self-registration
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.student_id = self.cleaned_data['student_id']
        user.set_password(self.cleaned_data['password1'])  # Explicitly set password
        if commit:
            user.save()
        return user


class AdminInstructorForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'})
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'department']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Department'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError('Passwords do not match')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'INSTRUCTOR'
        user.set_password(self.cleaned_data['password1'])
        user.is_active = True
        if commit:
            user.save()
        return user


class AdminUserEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'department', 'employee_id', 'student_id', 'role', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'student_id': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PasswordResetRequestForm(forms.Form):
    username_or_email = forms.CharField(
        label='Email or Username',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Email or username'})
    )

    def clean_username_or_email(self):
        value = self.cleaned_data['username_or_email']
        try:
            return CustomUser.objects.get(email=value)
        except CustomUser.DoesNotExist:
            try:
                return CustomUser.objects.get(username=value)
            except CustomUser.DoesNotExist:
                raise ValidationError('No account found with that email or username.')


class AdminPasswordResetForm(forms.Form):
    new_password = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New password'})
    )
    confirm_password = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'})
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('new_password') != cleaned_data.get('confirm_password'):
            raise ValidationError('Passwords do not match')
        return cleaned_data


class InstructorSubjectForm(forms.ModelForm):
    class Meta:
        model = FaceSubject
        fields = ['code', 'name', 'semester', 'school_year', 'is_archived']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject code'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject name'}),
            'semester': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Semester'}),
            'school_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'School year'}),
            'is_archived': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'department', 'phone_number']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Current password'}),
        label="Current Password"
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New password'}),
        label="New Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'}),
        label="Confirm New Password"
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError("New passwords do not match")

        return cleaned_data
