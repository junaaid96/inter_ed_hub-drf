# Generated by Django 4.2.7 on 2024-03-18 09:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teachers', '0003_alter_teacher_phone'),
    ]

    operations = [
        migrations.AlterField(
            model_name='teacher',
            name='phone',
            field=models.CharField(max_length=15),
        ),
    ]
