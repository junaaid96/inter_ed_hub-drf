from django.contrib import admin

from .models import Teacher


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'designation', 'department', 'created_at')
    list_filter = ('department',)
    search_fields = ('user__first_name', 'user__last_name', 'user__username', 'designation')
