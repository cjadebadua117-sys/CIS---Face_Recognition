import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cis_project.settings')
django.setup()

from accounts.models import Subject

# Second Year, Second Semester (Sections A, B)
year2_sem2_subjects = [
    ('ISCC 105', 'Information Management 1', 'Year 2'),
    ('ISPC 104', 'Information Technology Infrastructure and Network Technologies', 'Year 2'),
    ('ISCC 106', 'Application Development and Emerging Technologies', 'Year 2'),
    ('ISAE 102', 'Information System Innovations and New Technologies', 'Year 2'),
    ('ISAE 103', 'Object Oriented Programming', 'Year 2'),
    ('ISAE 104', 'Principles of Accounting', 'Year 2'),
    ('GEEC 112', 'The Entrepreneurial Mind', 'Year 2'),
    ('PATHFIT 104', 'Outdoor and Adventure Activities', 'Year 2'),
]

def create_subjects():
    # Create Year 2, Second Semester subjects (A, B)
    for code, title, _ in year2_sem2_subjects:
        for section in ['A', 'B']:
            try:
                Subject.objects.get_or_create(
                    code=code,
                    year_level='2',
                    section=section,
                    defaults={'title': title}
                )
            except Exception as e:
                print(f"Error creating {code} for Year 2 {section}: {e}")

    print("Subject data populated successfully!")

if __name__ == '__main__':
    create_subjects()