from django.db.models import Avg, Count, IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import serializers

from accounts.serializers import PersonSerializer, profile_of
from department.models import Department
from uploads.models import MediaAsset

from .models import Comment, Course, Enrollment, Lesson, LessonProgress, Note, Review, Section


def _scalar(queryset, group_field, aggregate, output_field=IntegerField()):
    """Correlated subquery returning one aggregate per course.

    Using subqueries (rather than joins) keeps counts correct when several
    to-many relations are aggregated at once.
    """
    return Coalesce(
        Subquery(queryset.values(group_field).annotate(v=aggregate).values('v')[:1],
                 output_field=output_field),
        Value(0), output_field=output_field)


def annotate_course_stats(queryset):
    from django.db.models import FloatField

    lessons = Lesson.objects.filter(section__course=OuterRef('pk')).order_by()
    return queryset.select_related('teacher__user', 'teacher__avatar', 'department', 'cover').annotate(
        student_count=_scalar(Enrollment.objects.filter(course=OuterRef('pk')).order_by(),
                              'course', Count('id')),
        review_count=_scalar(Review.objects.filter(course=OuterRef('pk')).order_by(),
                             'course', Count('id')),
        rating=_scalar(Review.objects.filter(course=OuterRef('pk')).order_by(),
                       'course', Avg('rating'), FloatField()),
        lesson_count=_scalar(lessons, 'section__course', Count('id')),
        total_seconds=_scalar(lessons, 'section__course', Sum('duration_seconds')),
    )


def cover_url(course):
    if course.cover_id and course.cover.is_ready:
        return course.cover.public_url()
    return course.cover_url or None


class DepartmentMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'slug', 'icon']


class CourseCardSerializer(serializers.ModelSerializer):
    cover = serializers.SerializerMethodField()
    teacher = PersonSerializer(read_only=True)
    department = DepartmentMiniSerializer(read_only=True)
    student_count = serializers.IntegerField(read_only=True, default=0)
    review_count = serializers.IntegerField(read_only=True, default=0)
    rating = serializers.SerializerMethodField()
    lesson_count = serializers.IntegerField(read_only=True, default=0)
    total_seconds = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Course
        fields = ['id', 'slug', 'title', 'subtitle', 'cover', 'level', 'language', 'teacher',
                  'department', 'student_count', 'review_count', 'rating', 'lesson_count',
                  'total_seconds', 'is_published', 'created_at', 'updated_at']

    def get_cover(self, course):
        return cover_url(course)

    def get_rating(self, course):
        return round(getattr(course, 'rating', 0) or 0, 2)


class LessonOutlineSerializer(serializers.ModelSerializer):
    has_video = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'kind', 'summary', 'duration_seconds', 'is_preview', 'has_video',
                  'order']


class SectionOutlineSerializer(serializers.ModelSerializer):
    lessons = LessonOutlineSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = ['id', 'title', 'order', 'lessons']


def course_progress(student, course):
    total = Lesson.objects.filter(section__course=course).count()
    done = LessonProgress.objects.filter(student=student, lesson__section__course=course,
                                         completed=True).count()
    return done, total, round(100 * done / total) if total else 0


class CourseDetailSerializer(CourseCardSerializer):
    sections = serializers.SerializerMethodField()
    viewer = serializers.SerializerMethodField()
    rating_breakdown = serializers.SerializerMethodField()
    teacher_profile = serializers.SerializerMethodField()

    class Meta(CourseCardSerializer.Meta):
        fields = CourseCardSerializer.Meta.fields + [
            'description', 'outcomes', 'requirements', 'credit', 'sections', 'viewer',
            'rating_breakdown', 'teacher_profile']

    def get_sections(self, course):
        sections = course.sections.prefetch_related('lessons__video')
        return SectionOutlineSerializer(sections, many=True).data

    def get_teacher_profile(self, course):
        t = course.teacher
        return {'bio': t.bio, 'designation': t.designation,
                'course_count': t.courses.filter(is_published=True).count()}

    def get_rating_breakdown(self, course):
        counts = dict(course.reviews.order_by().values_list('rating').annotate(n=Count('id')))
        return {str(star): counts.get(star, 0) for star in range(5, 0, -1)}

    def get_viewer(self, course):
        request = self.context.get('request')
        user = request.user if request else None
        profile = profile_of(user)
        viewer = {'role': getattr(profile, 'role', None), 'is_owner': False,
                  'is_enrolled': False, 'progress': 0, 'completed_lessons': [],
                  'last_lesson_id': None, 'review': None, 'certificate_code': None}
        if profile is None:
            return viewer
        if profile.role == 'teacher':
            viewer['is_owner'] = course.teacher_id == profile.pk
            return viewer
        enrollment = (Enrollment.objects.filter(student=profile, course=course)
                      .select_related('certificate').first())
        if enrollment is None:
            return viewer
        _, _, percent = course_progress(profile, course)
        review = Review.objects.filter(course=course, student=profile).first()
        viewer.update(
            is_enrolled=True, progress=percent,
            completed_lessons=list(LessonProgress.objects.filter(
                student=profile, lesson__section__course=course, completed=True)
                .values_list('lesson_id', flat=True)),
            last_lesson_id=enrollment.last_lesson_id,
            review=ReviewSerializer(review).data if review else None,
            certificate_code=getattr(getattr(enrollment, 'certificate', None), 'code', None),
        )
        return viewer


class CourseWriteSerializer(serializers.ModelSerializer):
    cover_id = serializers.PrimaryKeyRelatedField(
        source='cover', queryset=MediaAsset.objects.filter(kind=MediaAsset.Kind.IMAGE),
        required=False, allow_null=True)
    outcomes = serializers.ListField(child=serializers.CharField(max_length=200),
                                     required=False, max_length=20)
    requirements = serializers.ListField(child=serializers.CharField(max_length=200),
                                         required=False, max_length=20)

    class Meta:
        model = Course
        fields = ['title', 'subtitle', 'description', 'department', 'level', 'language',
                  'cover_id', 'cover_url', 'outcomes', 'requirements', 'credit', 'is_published']

    def validate_cover_id(self, asset):
        user = self.context['request'].user
        if asset and (asset.owner_id != user.pk or not asset.is_ready):
            raise serializers.ValidationError('Upload the cover image first.')
        return asset

    def validate(self, data):
        publishing = data.get('is_published', getattr(self.instance, 'is_published', False))
        if publishing:
            has_lessons = (self.instance is not None and
                           Lesson.objects.filter(section__course=self.instance).exists())
            if not has_lessons:
                raise serializers.ValidationError(
                    {'is_published': 'Add at least one lesson before publishing.'})
        return data


class StudioLessonSerializer(serializers.ModelSerializer):
    video_id = serializers.PrimaryKeyRelatedField(
        source='video', queryset=MediaAsset.objects.filter(kind=MediaAsset.Kind.VIDEO),
        required=False, allow_null=True)
    video = serializers.SerializerMethodField()
    has_video = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lesson
        fields = ['id', 'section', 'title', 'kind', 'summary', 'body', 'video_id', 'video',
                  'external_video_url', 'duration_seconds', 'is_preview', 'order', 'has_video']
        read_only_fields = ['section']

    def get_video(self, lesson):
        v = lesson.video
        if not v:
            return None
        return {'id': str(v.id), 'name': v.original_name, 'size': v.size, 'status': v.status,
                'duration_seconds': v.duration_seconds}

    def validate_video_id(self, asset):
        user = self.context['request'].user
        if asset and (asset.owner_id != user.pk or not asset.is_ready):
            raise serializers.ValidationError('Finish uploading the video first.')
        return asset

    def save(self, **kwargs):
        lesson = super().save(**kwargs)
        if lesson.video_id and lesson.video.duration_seconds and not lesson.duration_seconds:
            lesson.duration_seconds = lesson.video.duration_seconds
            lesson.save(update_fields=['duration_seconds'])
        return lesson


class StudioSectionSerializer(serializers.ModelSerializer):
    lessons = StudioLessonSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = ['id', 'title', 'order', 'lessons']


class StudioCourseSerializer(CourseCardSerializer):
    sections = serializers.SerializerMethodField()
    cover_id = serializers.UUIDField(read_only=True)

    class Meta(CourseCardSerializer.Meta):
        fields = CourseCardSerializer.Meta.fields + [
            'description', 'outcomes', 'requirements', 'credit', 'cover_id', 'cover_url',
            'sections']

    def get_sections(self, course):
        sections = course.sections.prefetch_related('lessons__video')
        return StudioSectionSerializer(sections, many=True, context=self.context).data

    def to_representation(self, course):
        data = super().to_representation(course)
        data['department'] = course.department_id
        data['department_detail'] = (DepartmentMiniSerializer(course.department).data
                                     if course.department else None)
        return data


class LessonPlayerSerializer(serializers.ModelSerializer):
    has_video = serializers.BooleanField(read_only=True)
    section_title = serializers.CharField(source='section.title', read_only=True)

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'kind', 'summary', 'body', 'duration_seconds', 'is_preview',
                  'has_video', 'section', 'section_title']


class NoteSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)

    class Meta:
        model = Note
        fields = ['id', 'lesson', 'lesson_title', 'timestamp_seconds', 'body', 'created_at',
                  'updated_at']
        read_only_fields = ['lesson']


class CommentAuthorField(serializers.Field):
    def to_representation(self, user):
        profile = profile_of(user)
        data = PersonSerializer(profile).data if profile else {
            'id': None, 'name': user.get_full_name() or user.username, 'avatar': None,
            'headline': ''}
        data['role'] = getattr(profile, 'role', 'admin')
        return data


class CommentSerializer(serializers.ModelSerializer):
    author = CommentAuthorField(read_only=True)
    replies = serializers.SerializerMethodField()
    is_instructor = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'author', 'body', 'timestamp_seconds', 'parent', 'created_at', 'replies',
                  'is_instructor']

    def get_replies(self, comment):
        if comment.parent_id:
            return []
        return CommentSerializer(comment.replies.select_related('author'), many=True,
                                 context=self.context).data

    def get_is_instructor(self, comment):
        teacher = getattr(comment.author, 'teacher', None)
        return bool(teacher and teacher.pk == comment.lesson.section.course.teacher_id)


class ReviewSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'rating', 'comment', 'student', 'created_at', 'updated_at']

    def get_student(self, review):
        return PersonSerializer(review.student).data
