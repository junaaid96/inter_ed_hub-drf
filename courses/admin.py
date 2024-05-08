from django.contrib import admin
from .models import Course
from .models import CourseProgress

# Register your models here.


class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'department', 'teacher', 'total_enrollment')
    list_filter = ('teacher', 'department')
    search_fields = ('title', 'department__slug', 'teacher__user__first_name',
                     'teacher__user__last_name')


class CourseProgressAdmin(admin.ModelAdmin):
    list_display = ('id', 'course', 'student', 'completed', 'progress')
    list_filter = ('course', 'student')
    search_fields = ('course__title', 'student__user__first_name',
                     'student__user__last_name')


admin.site.register(Course, CourseAdmin)
admin.site.register(CourseProgress, CourseProgressAdmin)
