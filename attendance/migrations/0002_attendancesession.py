# Generated manually for AttendanceSession model

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AttendanceSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=django.utils.timezone.now)),
                ('is_open', models.BooleanField(default=False)),
                ('opened_at', models.DateTimeField(blank=True, null=True)),
                ('opened_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='opened_sessions', to=settings.AUTH_USER_MODEL)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('closed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='closed_sessions', to=settings.AUTH_USER_MODEL)),
                ('grace_period_minutes', models.PositiveIntegerField(default=15)),
                ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_sessions', to='attendance.schedule')),
            ],
            options={
                'ordering': ['-date', '-opened_at'],
                'unique_together': {('schedule', 'date')},
            },
        ),
    ]