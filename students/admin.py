from django.contrib import admin
from .models import Student

# Register your models here.


class StudentAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'phone')
    search_fields = ('user__first_name', 'user__last_name', 'phone')

    def full_name(self, obj):
        return f'{obj.user.first_name} {obj.user.last_name}'


admin.site.register(Student, StudentAdmin)
