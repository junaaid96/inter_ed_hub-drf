from django.contrib import admin
from .models import Teacher

# Register your models here.


class TeacherAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'designation', 'phone')
    list_filter = ('designation',)
    search_fields = ('user__first_name', 'user__last_name',
                     'designation', 'phone')

    def full_name(self, obj):
        return f'{obj.user.first_name} {obj.user.last_name}'


admin.site.register(Teacher, TeacherAdmin)
