# Generated by Django 4.2.7 on 2024-03-29 13:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0002_course_department'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='credit',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='course',
            name='duration',
            field=models.IntegerField(null=True),
        ),
    ]
