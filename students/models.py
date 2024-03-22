from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_pic = models.ImageField(upload_to='students/images/', blank=True)
    bio = models.TextField()
    phone = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return f'{self.user.first_name} {self.user.last_name}'
