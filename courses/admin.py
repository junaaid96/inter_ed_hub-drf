from django.contrib import admin

from .models import (Certificate, Comment, Course, Enrollment, LearningActivity, Lesson,
                     LessonProgress, Note, Review, Section)


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'department', 'level', 'is_published', 'created_at')
    list_filter = ('is_published', 'level', 'department')
    search_fields = ('title', 'teacher__user__first_name', 'teacher__user__last_name')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [SectionInline]


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ('title', 'kind', 'duration_seconds', 'is_preview', 'order')


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order')
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'section', 'kind', 'duration_seconds', 'is_preview')
    list_filter = ('kind', 'is_preview')
    search_fields = ('title',)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_at', 'completed_at')
    list_filter = ('course',)


admin.site.register([LessonProgress, LearningActivity, Note, Comment, Review, Certificate])
