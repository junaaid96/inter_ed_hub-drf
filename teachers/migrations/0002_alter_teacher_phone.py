# Generated by Django 4.2.7 on 2024-03-18 03:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teachers', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='teacher',
            name='phone',
            field=models.IntegerField(max_length=15),
        ),
    ]
