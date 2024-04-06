from django.contrib import admin
from .models import Course

# Register your models here.


class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'department', 'teacher', 'total_enrollment')
    list_filter = ('teacher', 'department')
    search_fields = ('title', 'department__slug', 'teacher__user__first_name',
                     'teacher__user__last_name')


admin.site.register(Course, CourseAdmin)
