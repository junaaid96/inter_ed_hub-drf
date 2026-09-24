from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'department', 'created_at')
    list_filter = ('department',)
    search_fields = ('user__first_name', 'user__last_name', 'user__username', 'user__email')
