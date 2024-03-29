from django.db import models
from teachers.models import Teacher

# Create your models here.


class Course(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    duration = models.IntegerField(null=True)
    credit = models.IntegerField(null=True)
    department = models.CharField(max_length=100, null=True)
    image = models.ImageField(upload_to='courses/images/', blank=True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.title} by {self.teacher}'
