from django.db import models
from teachers.models import Teacher
from department.models import Department
from students.models import Student

# Create your models here.


class Course(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    duration = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    credit = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, null=True)
    image = models.ImageField(upload_to='courses/images/', blank=True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    total_enrollment = models.IntegerField(default=0)
    enrolled_students = models.ManyToManyField(Student, blank=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f'{self.title} by {self.teacher}'


class CourseProgress(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    progress = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        unique_together = ['course', 'student']

    def __str__(self):
        return f'{self.student} - {self.course}'
