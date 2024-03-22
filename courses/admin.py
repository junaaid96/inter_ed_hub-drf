from django.contrib import admin
from .models import Course

# Register your models here.


class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'teacher')
    list_filter = ('teacher',)
    search_fields = ('title', 'teacher__user__first_name',
                     'teacher__user__last_name')


admin.site.register(Course, CourseAdmin)
