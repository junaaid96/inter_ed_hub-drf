# Generated by Django 4.2.7 on 2024-03-30 00:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0004_alter_course_credit_alter_course_duration'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='department_slug',
            field=models.SlugField(max_length=100, null=True, unique=True),
        ),
    ]
