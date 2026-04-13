import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cis_project.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
print('User count:', User.objects.count())
for u in User.objects.all()[:5]:
    print('pk:', u.pk, 'username:', u.username, 'email:', u.email, 'active:', u.is_active, 'password hash length:', len(u.password) if u.password else 0)
