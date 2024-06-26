from django.db import models
from django.contrib.auth.models import User
from department.models import Department

# Create your models here.


class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_pic = models.ImageField(
        upload_to='teachers/images/', default='teachers/images/default.jpg', blank=True, null=True)
    bio = models.TextField()
    designation = models.CharField(max_length=100)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, null=True)
    phone = models.CharField(max_length=15)
    user_type = models.CharField(
        default='Teacher', max_length=10, editable=False)

    def __str__(self):
        return f'{self.user.first_name} {self.user.last_name}'
