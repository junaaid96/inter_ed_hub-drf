import secrets

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

from department.models import Department
from students.models import Student
from teachers.models import Teacher
from uploads.models import MediaAsset


class Course(models.Model):
    class Level(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'
        ALL = 'all', 'All levels'

    title = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True)
    subtitle = models.CharField(max_length=220, blank=True)
    description = models.TextField()
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='courses')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.ALL)
    language = models.CharField(max_length=40, default='English')
    cover = models.ForeignKey(MediaAsset, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='+')
    # Fallback artwork for seeded/demo courses that have no uploaded cover.
    cover_url = models.URLField(blank=True)
    outcomes = models.JSONField(default=list, blank=True)
    requirements = models.JSONField(default=list, blank=True)
    credit = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['is_published', '-created_at'])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:140] or 'course'
            slug, n = base, 2
            while Course.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f'{base}-{n}', n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def lessons(self):
        return Lesson.objects.filter(section__course=self)


class Section(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=140)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.course} / {self.title}'


class Lesson(models.Model):
    class Kind(models.TextChoices):
        VIDEO = 'video', 'Video'
        ARTICLE = 'article', 'Article'

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=160)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.VIDEO)
    summary = models.TextField(blank=True)
    # Markdown body for article lessons, or show notes for videos.
    body = models.TextField(blank=True)
    video = models.ForeignKey(MediaAsset, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='lessons')
    # Public video URL for demo content; uploaded videos use `video`.
    external_video_url = models.URLField(blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    is_preview = models.BooleanField(default=False,
                                     help_text='Free preview for visitors who are not enrolled.')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['section__order', 'order', 'id']

    def __str__(self):
        return self.title

    @property
    def course(self):
        return self.section.course

    @property
    def has_video(self):
        return bool((self.video_id and self.video.is_ready) or self.external_video_url)


class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    last_lesson = models.ForeignKey(Lesson, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['student', 'course']
        ordering = ['-last_accessed_at', '-enrolled_at']

    def __str__(self):
        return f'{self.student} → {self.course}'


class LessonProgress(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress')
    position_seconds = models.FloatField(default=0)
    watched_seconds = models.FloatField(default=0)
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'lesson']


class LearningActivity(models.Model):
    """Seconds of learning per student per day: powers streaks and charts."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='activity')
    date = models.DateField()
    seconds = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ['student', 'date']
        ordering = ['-date']


class Note(models.Model):
    """Private, timestamped note a learner pins to a moment in a lesson."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='notes')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='notes')
    timestamp_seconds = models.FloatField(default=0)
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['timestamp_seconds', 'created_at']


class Comment(models.Model):
    """Lesson discussion thread (one level of replies)."""

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='replies')
    body = models.TextField(max_length=4000)
    timestamp_seconds = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class Review(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['course', 'student']
        ordering = ['-updated_at']


def certificate_code():
    return secrets.token_hex(6).upper()


class Certificate(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE,
                                      related_name='certificate')
    code = models.CharField(max_length=16, unique=True, default=certificate_code)
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code
