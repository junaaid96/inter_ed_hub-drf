from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent, IsTeacher
from accounts.serializers import PersonSerializer, profile_of
from uploads.storage import get_storage

from .models import (Certificate, Comment, Course, Enrollment, LearningActivity, Lesson,
                     LessonProgress, Note, Review, Section)
from .serializers import (CommentSerializer, CourseCardSerializer, CourseDetailSerializer,
                          CourseWriteSerializer, LessonOutlineSerializer, LessonPlayerSerializer,
                          NoteSerializer, ReviewSerializer, StudioCourseSerializer,
                          StudioLessonSerializer, StudioSectionSerializer,
                          annotate_course_stats, course_progress)

DURATION_BUCKETS = {
    'short': Q(total_seconds__lt=2 * 3600),
    'medium': Q(total_seconds__gte=2 * 3600, total_seconds__lt=6 * 3600),
    'long': Q(total_seconds__gte=6 * 3600),
}
ORDERINGS = {
    'newest': ['-created_at'],
    'popular': ['-student_count', '-created_at'],
    'rating': ['-rating', '-review_count'],
    'title': ['title'],
}


def owned_course(request, slug):
    course = get_object_or_404(Course, slug=slug)
    teacher = getattr(request.user, 'teacher', None)
    if teacher is None or course.teacher_id != teacher.pk:
        raise PermissionDenied('You can only manage your own courses.')
    return course


def lesson_access(request, lesson):
    """Return (student_profile_or_None, is_owner). Raises when access is denied."""
    course = lesson.section.course
    user = request.user
    teacher = getattr(user, 'teacher', None) if user.is_authenticated else None
    if teacher and course.teacher_id == teacher.pk:
        return None, True
    student = getattr(user, 'student', None) if user.is_authenticated else None
    enrolled = bool(student and Enrollment.objects.filter(student=student, course=course).exists())
    if not course.is_published and not enrolled:
        raise PermissionDenied('This course is not available.')
    if enrolled:
        return student, False
    if lesson.is_preview:
        return None, False
    raise PermissionDenied('Enroll in this course to watch this lesson.')


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class CourseListCreateView(generics.ListCreateAPIView):
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'subtitle', 'description', 'teacher__user__first_name',
                     'teacher__user__last_name', 'department__name']

    def get_permissions(self):
        return [IsTeacher()] if self.request.method == 'POST' else [AllowAny()]

    def get_serializer_class(self):
        return CourseWriteSerializer if self.request.method == 'POST' else CourseCardSerializer

    def get_queryset(self):
        qs = annotate_course_stats(Course.objects.filter(is_published=True))
        params = self.request.query_params
        if params.get('department'):
            qs = qs.filter(department__slug__in=params['department'].split(','))
        if params.get('level'):
            qs = qs.filter(level__in=params['level'].split(','))
        if params.get('teacher'):
            qs = qs.filter(teacher_id=params['teacher'])
        if params.get('duration') in DURATION_BUCKETS:
            qs = qs.filter(DURATION_BUCKETS[params['duration']])
        if params.get('min_rating'):
            qs = qs.filter(rating__gte=float(params['min_rating']))
        return qs.order_by(*ORDERINGS.get(params.get('ordering'), ORDERINGS['popular']))

    def create(self, request, *args, **kwargs):
        serializer = CourseWriteSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        course = serializer.save(teacher=request.user.teacher)
        course = annotate_course_stats(Course.objects.filter(pk=course.pk)).get()
        return Response(StudioCourseSerializer(course, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)


class CourseDetailView(APIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else [IsTeacher()]

    def get(self, request, slug):
        course = get_object_or_404(annotate_course_stats(Course.objects.all()), slug=slug)
        if not course.is_published:
            teacher = getattr(request.user, 'teacher', None)
            student = getattr(request.user, 'student', None)
            allowed = (teacher and teacher.pk == course.teacher_id) or (
                student and course.enrollments.filter(student=student).exists())
            if not allowed:
                return Response({'detail': 'Course not found.'}, status=404)
        return Response(CourseDetailSerializer(course, context={'request': request}).data)

    def patch(self, request, slug):
        course = owned_course(request, slug)
        serializer = CourseWriteSerializer(course, data=request.data, partial=True,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        course = annotate_course_stats(Course.objects.filter(pk=course.pk)).get()
        return Response(StudioCourseSerializer(course, context={'request': request}).data)

    def delete(self, request, slug):
        owned_course(request, slug).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EnrollView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, slug):
        course = get_object_or_404(Course, slug=slug, is_published=True)
        enrollment, created = Enrollment.objects.get_or_create(
            student=request.user.student, course=course,
            defaults={'last_accessed_at': timezone.now()})
        first = course.lessons().first()
        return Response({'enrolled': True, 'created': created,
                         'first_lesson_id': first.pk if first else None},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, slug):
        Enrollment.objects.filter(student=request.user.student, course__slug=slug).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer

    def get_permissions(self):
        return [IsStudent()] if self.request.method == 'POST' else [AllowAny()]

    def get_queryset(self):
        return (Review.objects.filter(course__slug=self.kwargs['slug'])
                .select_related('student__user', 'student__avatar'))

    def create(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        student = request.user.student
        if not Enrollment.objects.filter(student=student, course=course).exists():
            raise PermissionDenied('Enroll in the course before reviewing it.')
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review, _ = Review.objects.update_or_create(
            course=course, student=student,
            defaults={'rating': serializer.validated_data['rating'],
                      'comment': serializer.validated_data.get('comment', '')})
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Studio (teacher course builder)
# ---------------------------------------------------------------------------

class StudioCourseListView(generics.ListAPIView):
    permission_classes = [IsTeacher]
    serializer_class = CourseCardSerializer
    pagination_class = None

    def get_queryset(self):
        return annotate_course_stats(Course.objects.filter(teacher=self.request.user.teacher)
                                     ).order_by('-updated_at')


class StudioCourseDetailView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request, slug):
        owned_course(request, slug)
        course = annotate_course_stats(Course.objects.filter(slug=slug)).get()
        return Response(StudioCourseSerializer(course, context={'request': request}).data)


class SectionCreateView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, slug):
        course = owned_course(request, slug)
        serializer = StudioSectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.validated_data.get('order')
        if order is None:
            order = course.sections.count()
        section = serializer.save(course=course, order=order)
        return Response(StudioSectionSerializer(section).data, status=status.HTTP_201_CREATED)


class SectionDetailView(APIView):
    permission_classes = [IsTeacher]

    def get_section(self, request, pk):
        section = get_object_or_404(Section.objects.select_related('course'), pk=pk)
        owned_course(request, section.course.slug)
        return section

    def patch(self, request, pk):
        section = self.get_section(request, pk)
        serializer = StudioSectionSerializer(section, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(StudioSectionSerializer(section, context={'request': request}).data)

    def delete(self, request, pk):
        self.get_section(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LessonCreateView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, pk):
        section = get_object_or_404(Section.objects.select_related('course'), pk=pk)
        owned_course(request, section.course.slug)
        serializer = StudioLessonSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.validated_data.get('order')
        lesson = serializer.save(section=section,
                                 order=section.lessons.count() if order is None else order)
        return Response(StudioLessonSerializer(lesson, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)


class LessonDetailView(APIView):
    """GET: the player view of a lesson. PATCH/DELETE: studio edits."""

    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else [IsTeacher()]

    def get_lesson(self, pk):
        return get_object_or_404(
            Lesson.objects.select_related('section__course', 'video'), pk=pk)

    def get(self, request, pk):
        lesson = self.get_lesson(pk)
        student, is_owner = lesson_access(request, lesson)
        ordered = list(lesson.section.course.lessons().values_list('pk', flat=True))
        idx = ordered.index(lesson.pk)
        progress = None
        if student:
            p = LessonProgress.objects.filter(student=student, lesson=lesson).first()
            progress = {'position_seconds': p.position_seconds if p else 0,
                        'completed': p.completed if p else False}
        data = LessonPlayerSerializer(lesson).data
        data.update(
            course_slug=lesson.section.course.slug,
            prev_lesson_id=ordered[idx - 1] if idx > 0 else None,
            next_lesson_id=ordered[idx + 1] if idx + 1 < len(ordered) else None,
            index=idx + 1, total=len(ordered), progress=progress, is_owner=is_owner,
        )
        return Response(data)

    def patch(self, request, pk):
        lesson = self.get_lesson(pk)
        owned_course(request, lesson.section.course.slug)
        serializer = StudioLessonSerializer(lesson, data=request.data, partial=True,
                                            context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        lesson = self.get_lesson(pk)
        owned_course(request, lesson.section.course.slug)
        lesson.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReorderView(APIView):
    """Persist drag-and-drop ordering: {"sections": [{"id": 1, "lessons": [3, 1, 2]}]}."""

    permission_classes = [IsTeacher]

    @transaction.atomic
    def post(self, request, slug):
        course = owned_course(request, slug)
        section_ids = set(course.sections.values_list('pk', flat=True))
        lesson_ids = set(course.lessons().values_list('pk', flat=True))
        for s_index, item in enumerate(request.data.get('sections', [])):
            if item.get('id') not in section_ids:
                raise ValidationError('Unknown section.')
            Section.objects.filter(pk=item['id']).update(order=s_index)
            for l_index, lesson_id in enumerate(item.get('lessons', [])):
                if lesson_id not in lesson_ids:
                    raise ValidationError('Unknown lesson.')
                Lesson.objects.filter(pk=lesson_id).update(section_id=item['id'], order=l_index)
        return Response({'ok': True})


# ---------------------------------------------------------------------------
# Learning: streaming, progress, notes, discussion
# ---------------------------------------------------------------------------

class LessonStreamView(APIView):
    """Hand the player a short-lived URL. Bytes stream straight from storage,
    with HTTP range requests so learners can seek instantly."""

    permission_classes = [AllowAny]

    def get(self, request, pk):
        lesson = get_object_or_404(Lesson.objects.select_related('section__course', 'video'),
                                   pk=pk)
        lesson_access(request, lesson)
        if lesson.video_id and lesson.video.is_ready:
            ttl = settings.VIDEO_URL_TTL
            return Response({
                'url': get_storage().presign_get(lesson.video.key, expires=ttl),
                'content_type': lesson.video.content_type,
                'expires_in': ttl,
            })
        if lesson.external_video_url:
            return Response({'url': lesson.external_video_url, 'content_type': 'video/mp4',
                             'expires_in': None})
        return Response({'detail': 'This lesson has no video.'}, status=404)


MAX_HEARTBEAT_SECONDS = 90


def complete_course_if_done(enrollment):
    done, total, _ = course_progress(enrollment.student, enrollment.course)
    if total and done >= total and not enrollment.completed_at:
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=['completed_at'])
        Certificate.objects.get_or_create(enrollment=enrollment)


class LessonProgressView(APIView):
    """Heartbeat from the player: position for resume, watch time for streaks."""

    permission_classes = [IsStudent]

    @transaction.atomic
    def post(self, request, pk):
        lesson = get_object_or_404(Lesson.objects.select_related('section__course'), pk=pk)
        student = request.user.student
        enrollment = Enrollment.objects.filter(student=student,
                                               course=lesson.section.course).first()
        if enrollment is None:
            raise PermissionDenied('Enroll in this course first.')

        try:
            position = max(0.0, float(request.data.get('position_seconds', 0)))
            delta = min(max(0.0, float(request.data.get('delta_seconds', 0))),
                        MAX_HEARTBEAT_SECONDS)
        except (TypeError, ValueError):
            raise ValidationError('position_seconds and delta_seconds must be numbers.')

        progress, _ = LessonProgress.objects.select_for_update().get_or_create(
            student=student, lesson=lesson)
        progress.position_seconds = position
        progress.watched_seconds += delta
        duration = lesson.duration_seconds
        if request.data.get('completed') is True or (duration and position >= duration * 0.9):
            progress.completed = True
        elif request.data.get('completed') is False:
            progress.completed = False
        progress.save()

        if delta:
            activity, _ = LearningActivity.objects.get_or_create(
                student=student, date=timezone.localdate())
            LearningActivity.objects.filter(pk=activity.pk).update(
                seconds=F('seconds') + int(round(delta)))

        enrollment.last_lesson = lesson
        enrollment.last_accessed_at = timezone.now()
        enrollment.save(update_fields=['last_lesson', 'last_accessed_at'])
        complete_course_if_done(enrollment)
        enrollment.refresh_from_db()

        _, _, percent = course_progress(student, lesson.section.course)
        cert = Certificate.objects.filter(enrollment=enrollment).first()
        return Response({'completed': progress.completed, 'course_progress': percent,
                         'certificate_code': cert.code if cert else None})


class NoteListCreateView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk):
        notes = Note.objects.filter(student=request.user.student, lesson_id=pk)
        return Response(NoteSerializer(notes.select_related('lesson'), many=True).data)

    def post(self, request, pk):
        lesson = get_object_or_404(Lesson.objects.select_related('section__course'), pk=pk)
        lesson_access(request, lesson)
        serializer = NoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.save(student=request.user.student, lesson=lesson)
        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)


class CourseNotesView(APIView):
    """Every note a learner took in a course, for review/export."""

    permission_classes = [IsStudent]

    def get(self, request, slug):
        notes = (Note.objects.filter(student=request.user.student, lesson__section__course__slug=slug)
                 .select_related('lesson').order_by('lesson__section__order', 'lesson__order',
                                                    'timestamp_seconds'))
        return Response(NoteSerializer(notes, many=True).data)


class NoteDetailView(APIView):
    permission_classes = [IsStudent]

    def patch(self, request, pk):
        note = get_object_or_404(Note, pk=pk, student=request.user.student)
        serializer = NoteSerializer(note, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        get_object_or_404(Note, pk=pk, student=request.user.student).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommentListCreateView(APIView):
    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method == 'POST' else [AllowAny()]

    def get(self, request, pk):
        lesson = get_object_or_404(Lesson.objects.select_related('section__course'), pk=pk)
        lesson_access(request, lesson)
        comments = (lesson.comments.filter(parent__isnull=True)
                    .select_related('author', 'lesson__section__course').order_by('-created_at'))
        return Response(CommentSerializer(comments, many=True).data)

    def post(self, request, pk):
        lesson = get_object_or_404(Lesson.objects.select_related('section__course'), pk=pk)
        lesson_access(request, lesson)
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parent = serializer.validated_data.get('parent')
        if parent and (parent.lesson_id != lesson.pk or parent.parent_id):
            raise ValidationError('You can only reply to a top-level comment on this lesson.')
        comment = serializer.save(author=request.user, lesson=lesson)
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class CommentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        comment = get_object_or_404(Comment.objects.select_related('lesson__section__course'),
                                    pk=pk)
        teacher = getattr(request.user, 'teacher', None)
        is_course_teacher = teacher and comment.lesson.section.course.teacher_id == teacher.pk
        if comment.author_id != request.user.pk and not is_course_teacher:
            raise PermissionDenied('You cannot delete this comment.')
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Dashboards & certificates
# ---------------------------------------------------------------------------

def streaks(dates):
    """(current, longest) streak of consecutive learning days."""
    days = sorted(set(dates))
    longest = run = 0
    prev = None
    for day in days:
        run = run + 1 if prev and day - prev == timedelta(days=1) else 1
        longest = max(longest, run)
        prev = day
    today = timezone.localdate()
    current = 0
    if days and (today - days[-1]).days <= 1:
        current, cursor = 0, days[-1]
        day_set = set(days)
        while cursor in day_set:
            current += 1
            cursor -= timedelta(days=1)
    return current, longest


class MyLearningView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        student = request.user.student
        today = timezone.localdate()
        activity = list(LearningActivity.objects.filter(student=student, seconds__gt=0)
                        .values_list('date', 'seconds'))
        current, longest = streaks([d for d, _ in activity])
        window_start = today - timedelta(days=83)
        by_day = {d: s for d, s in activity if d >= window_start}

        enrollments = (Enrollment.objects.filter(student=student)
                       .select_related('course__teacher__user', 'course__teacher__avatar',
                                       'course__cover', 'course__department', 'last_lesson',
                                       'certificate'))
        courses = []
        for e in enrollments:
            done, total, percent = course_progress(student, e.course)
            next_lesson = e.last_lesson
            if next_lesson is None or LessonProgress.objects.filter(
                    student=student, lesson=next_lesson, completed=True).exists():
                next_lesson = (e.course.lessons().exclude(
                    progress__student=student, progress__completed=True).first()
                    or next_lesson)
            courses.append({
                'course': CourseCardSerializer(e.course).data,
                'progress': percent, 'completed_lessons': done, 'total_lessons': total,
                'enrolled_at': e.enrolled_at, 'last_accessed_at': e.last_accessed_at,
                'completed_at': e.completed_at,
                'next_lesson': LessonOutlineSerializer(next_lesson).data if next_lesson else None,
                'certificate_code': getattr(getattr(e, 'certificate', None), 'code', None),
            })

        week_seconds = sum(s for d, s in activity if d > today - timedelta(days=7))
        return Response({
            'stats': {
                'enrolled': len(courses),
                'completed': sum(1 for c in courses if c['completed_at']),
                'current_streak': current,
                'longest_streak': longest,
                'minutes_this_week': round(week_seconds / 60),
                'total_minutes': round(sum(s for _, s in activity) / 60),
                'notes': Note.objects.filter(student=student).count(),
            },
            'activity': [{'date': day, 'seconds': by_day.get(day, 0),
                          'minutes': round(by_day.get(day, 0) / 60)}
                         for day in (window_start + timedelta(days=i) for i in range(84))],
            'courses': courses,
        })


class MyTeachingView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request):
        teacher = request.user.teacher
        courses = annotate_course_stats(Course.objects.filter(teacher=teacher)).order_by('-updated_at')
        rows = []
        for course in courses:
            completed = course.enrollments.filter(completed_at__isnull=False).count()
            rows.append({**CourseCardSerializer(course).data,
                         'completion_rate': round(100 * completed / course.student_count)
                         if course.student_count else 0})
        enrollments = Enrollment.objects.filter(course__teacher=teacher)
        reviews = Review.objects.filter(course__teacher=teacher)
        since = timezone.now() - timedelta(days=30)
        daily = (enrollments.filter(enrolled_at__gte=since).order_by()
                 .annotate(day=TruncDate('enrolled_at')).values('day')
                 .annotate(n=Count('id')))
        daily_map = {str(row['day']): row['n'] for row in daily}
        today = timezone.localdate()
        questions = (Comment.objects.filter(lesson__section__course__teacher=teacher,
                                            parent__isnull=True)
                     .exclude(author=request.user)
                     .annotate(teacher_replies=Count('replies', filter=Q(
                         replies__author=request.user)))
                     .select_related('author', 'lesson__section__course')
                     .order_by('teacher_replies', '-created_at')[:8])
        watch = LessonProgress.objects.filter(lesson__section__course__teacher=teacher)
        return Response({
            'stats': {
                'courses': len(rows),
                'published': sum(1 for c in rows if c['is_published']),
                'students': enrollments.values('student').distinct().count(),
                'enrollments': enrollments.count(),
                'rating': round(sum(r.rating for r in reviews) / reviews.count(), 2)
                if reviews.exists() else 0,
                'reviews': reviews.count(),
                'watch_minutes': round(sum(watch.values_list('watched_seconds', flat=True)) / 60),
            },
            'enrollments_30d': [
                {'date': str(today - timedelta(days=29 - i)),
                 'count': daily_map.get(str(today - timedelta(days=29 - i)), 0)}
                for i in range(30)],
            'courses': rows,
            'questions': [{
                **CommentSerializer(q).data,
                'answered': q.teacher_replies > 0,
                'lesson': {'id': q.lesson_id, 'title': q.lesson.title},
                'course': {'slug': q.lesson.section.course.slug,
                           'title': q.lesson.section.course.title},
            } for q in questions],
        })


class CertificateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, code):
        cert = get_object_or_404(
            Certificate.objects.select_related('enrollment__student__user',
                                               'enrollment__course__teacher__user'),
            code=code.upper())
        course = annotate_course_stats(Course.objects.filter(pk=cert.enrollment.course_id)).get()
        return Response({
            'code': cert.code,
            'issued_at': cert.issued_at,
            'student_name': str(cert.enrollment.student),
            'course': CourseCardSerializer(course).data,
            'teacher': PersonSerializer(course.teacher).data,
        })
