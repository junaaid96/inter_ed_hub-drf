from django.contrib.auth.models import User
from django.db import models

from department.models import Department
from uploads.models import MediaAsset


class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ForeignKey(MediaAsset, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='+')
    bio = models.TextField(blank=True)
    designation = models.CharField(max_length=100, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    role = 'teacher'

    def __str__(self):
        return self.user.get_full_name() or self.user.username
