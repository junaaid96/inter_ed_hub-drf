# Generated by Django 4.2.7 on 2024-05-08 11:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0003_student_user_type'),
        ('courses', '0009_course_enrolled_students'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('completed', models.BooleanField(default=False)),
                ('progress', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.course')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='students.student')),
            ],
            options={
                'unique_together': {('course', 'student')},
            },
        ),
    ]
