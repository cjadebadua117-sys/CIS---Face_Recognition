# Generated migration for Subject and StudentEnrollment models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_auditlog_ip_address'),
    ]

    operations = [
        # Add fields to CustomUser
        migrations.AddField(
            model_name='customuser',
            name='year_level',
            field=models.CharField(blank=True, choices=[('1', 'Year 1'), ('2', 'Year 2'), ('3', 'Year 3'), ('4', 'Year 4')], max_length=1, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='section',
            field=models.CharField(blank=True, choices=[('A', 'Section A'), ('B', 'Section B'), ('C', 'Section C')], max_length=1, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='enrollment_status',
            field=models.CharField(choices=[('NOT_ENROLLED', 'Not Enrolled'), ('PENDING', 'Pending Enrollment'), ('REGULAR', 'Regular'), ('IRREGULAR', 'Irregular')], default='NOT_ENROLLED', max_length=20),
        ),
        migrations.AddField(
            model_name='customuser',
            name='enrollment_completed_date',
            field=models.DateTimeField(blank=True, null=True),
        ),

        # Create Subject model
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('year_level', models.CharField(choices=[('1', 'Year 1'), ('2', 'Year 2'), ('3', 'Year 3'), ('4', 'Year 4')], max_length=1)),
                ('section', models.CharField(choices=[('A', 'Section A'), ('B', 'Section B'), ('C', 'Section C')], max_length=1)),
                ('description', models.TextField(blank=True)),
                ('units', models.PositiveIntegerField(default=3)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['year_level', 'section', 'code'],
            },
        ),

        # Add unique_together constraint to Subject
        migrations.AlterUniqueTogether(
            name='subject',
            unique_together={('code', 'year_level', 'section')},
        ),

        # Add index to Subject
        migrations.AddIndex(
            model_name='subject',
            index=models.Index(fields=['year_level', 'section'], name='accounts_su_year_le_idx'),
        ),

        # Create StudentEnrollment model
        migrations.CreateModel(
            name='StudentEnrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enrolled_date', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='accounts.customuser')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.subject')),
            ],
            options={
                'ordering': ['subject__year_level', 'subject__section', 'subject__code'],
            },
        ),

        # Add unique_together constraint to StudentEnrollment
        migrations.AlterUniqueTogether(
            name='studentenrollment',
            unique_together={('student', 'subject')},
        ),

        # Add index to StudentEnrollment
        migrations.AddIndex(
            model_name='studentenrollment',
            index=models.Index(fields=['student', 'is_active'], name='accounts_st_student_idx'),
        ),
    ]
