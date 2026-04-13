from django import forms
from .models import Department, Subject, Section, EnrollmentRequest


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'head']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Department name'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Department code'}),
            'head': forms.Select(attrs={'class': 'form-select'}),
        }


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['code', 'name', 'semester', 'school_year', 'is_archived']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject code'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject name'}),
            'semester': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Semester'}),
            'school_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'School year'}),
            'is_archived': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SectionForm(forms.ModelForm):
    DAYS_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]
    
    schedule_day = forms.ChoiceField(choices=DAYS_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    
    class Meta:
        model = Section
        fields = ['name', 'schedule_day', 'schedule_time', 'room']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Section name'}),
            'schedule_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'room': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Room'}),
        }


class EnrollmentRequestForm(forms.ModelForm):
    class Meta:
        model = EnrollmentRequest
        fields = ['appeal_message', 'appeal_evidence']
        widgets = {
            'appeal_message': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Explain why you want to appeal this decision...',
                'rows': 4
            }),
            'appeal_evidence': forms.FileInput(attrs={'class': 'form-control'}),
        }




class PersonEnrollmentForm(forms.Form):
    """Form for enrolling a person's face photos"""
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Full Name'
        })
    )
    person_id = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Person ID'
        })
    )
    department = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Department'
        })
    )
    role = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Role'
        })
    )
    photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )
