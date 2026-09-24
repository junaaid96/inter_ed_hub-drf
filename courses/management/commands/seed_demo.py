"""Populate an empty database with departments, instructors and courses.

    python manage.py seed_demo                 # catalog only (instructors can't log in)
    python manage.py seed_demo --demo-users    # also demo_teacher / demo_student logins

Demo lessons stream public sample videos; real courses use uploaded videos.
"""

import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from courses.models import Course, Enrollment, Lesson, Review, Section
from department.models import Department
from students.models import Student
from teachers.models import Teacher

SAMPLE_VIDEOS = [
    ('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4', 15),
    ('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4', 15),
    ('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4', 60),
    ('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4', 15),
    ('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4', 15),
    ('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4', 596),
    ('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4', 653),
]

DEPARTMENTS = [
    ('Music and Performing Arts', 'music-and-performing-arts', '🎻',
     'Explore music, theater and dance while honing performance skills.'),
    ('Mathematics and Statistics', 'mathematics-and-statistics', '∑',
     'Mathematical thinking and statistical analysis for finance, data and engineering.'),
    ('Language and Literature', 'language-and-literature', '📚',
     'Language, literature and communication through diverse literary works.'),
    ('Environmental Science and Sustainability', 'environmental-science-and-sustainability', '🌱',
     'Environmental issues, conservation and sustainable practice.'),
    ('Fine Arts', 'fine-arts', '🎨',
     'Painting, sculpture, photography and digital art.'),
    ('Computer Science', 'computer-science', '💻',
     'Programming, systems and the ideas behind modern software.'),
]

TEACHERS = [
    ('amara', 'Amara', 'Okafor', 'Professor of Applied Mathematics', 'mathematics-and-statistics'),
    ('lucas', 'Lucas', 'Meyer', 'Novelist & Writing Coach', 'language-and-literature'),
    ('sofia', 'Sofia', 'Rossi', 'Conductor, Vienna Chamber Choir', 'music-and-performing-arts'),
    ('kenji', 'Kenji', 'Tanaka', 'Climate Scientist', 'environmental-science-and-sustainability'),
    ('leila', 'Leila', 'Haddad', 'Painter & Art Historian', 'fine-arts'),
    ('noah', 'Noah', 'Bennett', 'Staff Software Engineer', 'computer-science'),
]

COURSES = [
    ('amara', 'Chess and Numbers: Strategy in Mathematics', 'intermediate',
     'Use the chessboard as a lab for combinatorics, probability and game theory.'),
    ('amara', 'Advanced Calculus: Theorems and Applications', 'advanced',
     'The fundamental theorems of calculus, proved and applied to real problems.'),
    ('lucas', 'Creative Writing: From Ideas to Publication', 'beginner',
     'Develop ideas, draft with confidence, revise ruthlessly and get published.'),
    ('lucas', 'The American Novel: A Literary Exploration', 'intermediate',
     'Themes and historical context in the great American novels.'),
    ('sofia', 'The World of Classical Music: An Auditory Experience', 'beginner',
     'From baroque to contemporary: learn to really listen.'),
    ('sofia', 'Choral Mastery: Techniques and Performance', 'all',
     'Vocal technique, blend and stage presence for choir singers.'),
    ('kenji', 'Sustainable Living: Environmental Science in Practice', 'beginner',
     'Evidence-based habits that shrink your footprint.'),
    ('kenji', 'Climate Change: Challenges and Solutions', 'intermediate',
     'The physics of warming, its impacts, and the solutions that scale.'),
    ('leila', 'The Artistic Process: From Concept to Canvas', 'all',
     'A hands-on path from first sketch to finished painting.'),
    ('leila', 'Art History: A Journey Through Time', 'beginner',
     'The movements that shaped how we see, from cave walls to pixels.'),
    ('noah', 'Modern Web Development with Django and Next.js', 'intermediate',
     'Build and ship a full-stack app with a Django API and a Next.js frontend.'),
]

SECTION_TEMPLATES = [
    ('Getting started', ['Welcome and course roadmap', 'How to get the most from this course']),
    ('Core ideas', ['The key concepts', 'Worked example', 'Common mistakes to avoid']),
    ('Putting it into practice', ['Guided project', 'Going further']),
]


class Command(BaseCommand):
    help = 'Seed departments, instructors and demo courses.'

    def add_arguments(self, parser):
        parser.add_argument('--demo-users', action='store_true',
                            help='Create demo_teacher and demo_student logins.')
        parser.add_argument('--password', default='learn-together-2026',
                            help='Password for demo logins.')

    @transaction.atomic
    def handle(self, *args, demo_users, password, **options):
        rng = random.Random(42)
        departments = {}
        for name, slug, icon, description in DEPARTMENTS:
            departments[slug], _ = Department.objects.update_or_create(
                slug=slug, defaults={'name': name, 'icon': icon, 'description': description})

        teachers = {}
        for username, first, last, designation, dept in TEACHERS:
            user, created = User.objects.get_or_create(
                username=username, defaults={'first_name': first, 'last_name': last,
                                             'email': f'{username}@example.com'})
            if created:
                user.set_unusable_password()
                user.save()
            teachers[username], _ = Teacher.objects.get_or_create(
                user=user, defaults={'designation': designation, 'department': departments[dept],
                                     'bio': f'{first} teaches {departments[dept].name.lower()} '
                                            'with a focus on practical, joyful learning.'})

        created_courses = 0
        for username, title, level, subtitle in COURSES:
            teacher = teachers[username]
            if Course.objects.filter(title=title, teacher=teacher).exists():
                continue
            course = Course.objects.create(
                title=title, subtitle=subtitle, teacher=teacher, level=level,
                department=teacher.department, is_published=True,
                description=f'{subtitle}\n\nThis course mixes short video lessons, readings '
                            'and practice so you can learn at your own pace and apply what '
                            'you learn right away.',
                cover_url=f'https://picsum.photos/seed/{title.split(":")[0].replace(" ", "")}/1200/675',
                outcomes=['Understand the core ideas and vocabulary',
                          'Apply techniques to realistic problems',
                          'Build a small portfolio project',
                          'Know where to go next'],
                requirements=['Curiosity and a notebook', 'No prior experience needed'],
                credit=rng.choice([1.5, 2, 3]),
            )
            for s_index, (section_title, lessons) in enumerate(SECTION_TEMPLATES):
                section = Section.objects.create(course=course, title=section_title, order=s_index)
                for l_index, lesson_title in enumerate(lessons):
                    url, seconds = rng.choice(SAMPLE_VIDEOS)
                    Lesson.objects.create(
                        section=section, title=lesson_title, order=l_index,
                        kind=Lesson.Kind.VIDEO, external_video_url=url, duration_seconds=seconds,
                        is_preview=s_index == 0,
                        summary=f'{lesson_title}, part of "{section_title}".',
                    )
            Lesson.objects.create(
                section=section, title='Reading: summary and resources', order=len(lessons),
                kind=Lesson.Kind.ARTICLE, duration_seconds=300,
                body=f'# {title}\n\nYou made it! Here is a recap of the key ideas and a '
                     'reading list to keep going.\n\n- Revisit your timestamped notes\n'
                     '- Share your project in the discussion\n- Leave a review to help others',
            )
            created_courses += 1

        if demo_users:
            self._demo_users(password, departments, rng)
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(departments)} departments, {len(teachers)} instructors, '
            f'{created_courses} new courses.'))

    def _demo_users(self, password, departments, rng):
        t_user, _ = User.objects.get_or_create(
            username='demo_teacher', defaults={'first_name': 'Dana', 'last_name': 'Teacher',
                                               'email': 'demo_teacher@example.com'})
        t_user.set_password(password)
        t_user.save()
        Teacher.objects.get_or_create(user=t_user, defaults={
            'designation': 'Demo Instructor', 'department': departments['computer-science']})

        s_user, _ = User.objects.get_or_create(
            username='demo_student', defaults={'first_name': 'Sam', 'last_name': 'Student',
                                               'email': 'demo_student@example.com'})
        s_user.set_password(password)
        s_user.save()
        student, _ = Student.objects.get_or_create(
            user=s_user, defaults={'department': departments['mathematics-and-statistics']})
        for course in Course.objects.filter(is_published=True).order_by('?')[:3]:
            Enrollment.objects.get_or_create(student=student, course=course,
                                             defaults={'last_accessed_at': timezone.now()})
            Review.objects.get_or_create(course=course, student=student, defaults={
                'rating': rng.choice([4, 5]), 'comment': 'Clear, practical and fun.'})
        self.stdout.write(f'Demo logins: demo_teacher / demo_student (password: {password})')
