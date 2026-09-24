import shutil
import tempfile
from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from courses.models import Certificate, Course, LearningActivity, Lesson, Section
from courses.views import streaks
from uploads.storage import get_storage

TEMP_STORAGE = tempfile.mkdtemp()


@override_settings(STORAGE_BACKEND='local', LOCAL_STORAGE_ROOT=TEMP_STORAGE,
                   BACKEND_URL='http://testserver', REQUIRE_EMAIL_ACTIVATION=False)
class LearningFlowTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_STORAGE, ignore_errors=True)

    def setUp(self):
        get_storage.cache_clear()

    def register(self, role, username):
        res = self.client.post('/auth/register/', {
            'role': role, 'username': username, 'email': f'{username}@example.com',
            'first_name': username.title(), 'password': 'correct-horse-battery'}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        return res.data['token']

    def as_user(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

    def upload_video(self, payload=b'\x00' * 2048):
        res = self.client.post('/uploads/', {'kind': 'video', 'filename': 'intro.mp4',
                                             'content_type': 'video/mp4', 'size': len(payload)},
                               format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['strategy'], 'single')
        put = self.client.generic('PUT', res.data['upload_url'].replace('http://testserver', ''),
                                  payload, content_type='video/mp4')
        self.assertEqual(put.status_code, 200)
        asset_id = res.data['asset']['id']
        done = self.client.post(f'/uploads/{asset_id}/complete/', {'duration_seconds': 100},
                                format='json')
        self.assertEqual(done.status_code, 200, done.data)
        self.assertEqual(done.data['status'], 'ready')
        return asset_id

    def build_course(self):
        teacher = self.register('teacher', 'tina')
        self.as_user(teacher)
        course = self.client.post('/courses/', {'title': 'Intro to Testing',
                                                'description': 'Learn tests'}, format='json')
        self.assertEqual(course.status_code, 201, course.data)
        slug = course.data['slug']

        publish_early = self.client.patch(f'/courses/{slug}/', {'is_published': True},
                                          format='json')
        self.assertEqual(publish_early.status_code, 400)

        section = self.client.post(f'/courses/{slug}/sections/', {'title': 'Basics'},
                                   format='json').data
        video_id = self.upload_video()
        l1 = self.client.post(f"/sections/{section['id']}/lessons/",
                              {'title': 'Welcome', 'video_id': video_id, 'is_preview': True},
                              format='json')
        self.assertEqual(l1.status_code, 201, l1.data)
        self.assertEqual(l1.data['duration_seconds'], 100)
        l2 = self.client.post(f"/sections/{section['id']}/lessons/",
                              {'title': 'Reading', 'kind': 'article', 'body': '# Hi'},
                              format='json')
        self.assertEqual(self.client.patch(f'/courses/{slug}/', {'is_published': True},
                                           format='json').status_code, 200)
        return teacher, slug, l1.data['id'], l2.data['id']

    def test_full_learning_journey(self):
        teacher, slug, video_lesson, article_lesson = self.build_course()

        # Anonymous visitors can watch the preview lesson but not the rest.
        self.client.credentials()
        self.assertEqual(self.client.get(f'/lessons/{video_lesson}/stream/').status_code, 200)
        self.assertEqual(self.client.get(f'/lessons/{article_lesson}/').status_code, 403)

        student = self.register('student', 'sam')
        self.as_user(student)
        catalog = self.client.get('/courses/?search=testing').data
        self.assertEqual(catalog['count'], 1)
        self.assertEqual(self.client.post(f'/courses/{slug}/enroll/').status_code, 201)

        stream = self.client.get(f'/lessons/{video_lesson}/stream/')
        self.assertEqual(stream.status_code, 200)
        ranged = self.client.get(stream.data['url'].replace('http://testserver', ''),
                                 HTTP_RANGE='bytes=0-99')
        self.assertEqual(ranged.status_code, 206)
        self.assertEqual(ranged['Content-Range'], 'bytes 0-99/2048')

        # Heartbeats: resume position is stored, 90% auto-completes.
        res = self.client.post(f'/lessons/{video_lesson}/progress/',
                               {'position_seconds': 30, 'delta_seconds': 30}, format='json')
        self.assertFalse(res.data['completed'])
        self.assertEqual(self.client.get(f'/lessons/{video_lesson}/').data['progress']
                         ['position_seconds'], 30)
        res = self.client.post(f'/lessons/{video_lesson}/progress/',
                               {'position_seconds': 95, 'delta_seconds': 500}, format='json')
        self.assertTrue(res.data['completed'])
        self.assertEqual(res.data['course_progress'], 50)
        self.assertEqual(LearningActivity.objects.get().seconds, 30 + 90)  # delta is capped

        note = self.client.post(f'/lessons/{video_lesson}/notes/',
                                {'timestamp_seconds': 12.5, 'body': 'Key idea'}, format='json')
        self.assertEqual(note.status_code, 201)
        self.assertEqual(len(self.client.get(f'/courses/{slug}/notes/').data), 1)

        question = self.client.post(f'/lessons/{video_lesson}/comments/',
                                    {'body': 'Why?'}, format='json').data

        res = self.client.post(f'/lessons/{article_lesson}/progress/', {'completed': True},
                               format='json')
        self.assertEqual(res.data['course_progress'], 100)
        code = res.data['certificate_code']
        self.assertTrue(Certificate.objects.filter(code=code).exists())

        review = self.client.post(f'/courses/{slug}/reviews/', {'rating': 5, 'comment': 'Great'},
                                  format='json')
        self.assertEqual(review.status_code, 201)

        learning = self.client.get('/me/learning/').data
        self.assertEqual(learning['stats']['completed'], 1)
        self.assertEqual(learning['stats']['current_streak'], 1)
        self.assertEqual(len(learning['activity']), 84)

        self.client.credentials()
        cert = self.client.get(f'/certificates/{code}/').data
        self.assertEqual(cert['student_name'], 'Sam')

        # Instructor sees the question and the rating, and replies as instructor.
        self.as_user(teacher)
        teaching = self.client.get('/me/teaching/').data
        self.assertEqual(teaching['stats']['students'], 1)
        self.assertEqual(teaching['stats']['rating'], 5)
        self.assertFalse(teaching['questions'][0]['answered'])
        reply = self.client.post(f'/lessons/{video_lesson}/comments/',
                                 {'body': 'Because!', 'parent': question['id']}, format='json')
        self.assertTrue(reply.data['is_instructor'])

        detail = self.client.get(f'/courses/{slug}/').data
        self.assertEqual(detail['rating_breakdown']['5'], 1)
        self.assertTrue(detail['viewer']['is_owner'])

    def test_only_owner_can_edit_and_students_cannot_upload_video(self):
        _, slug, video_lesson, _ = self.build_course()
        self.register('teacher', 'other')
        other = self.client.post('/auth/login/', {'login': 'other@example.com',
                                                  'password': 'correct-horse-battery'},
                                 format='json').data['token']
        self.as_user(other)
        self.assertEqual(self.client.patch(f'/courses/{slug}/', {'title': 'Hijack'},
                                           format='json').status_code, 403)
        self.assertEqual(self.client.delete(f'/lessons/{video_lesson}/').status_code, 403)

        self.as_user(self.register('student', 'stu'))
        res = self.client.post('/uploads/', {'kind': 'video', 'filename': 'x.mp4',
                                             'content_type': 'video/mp4', 'size': 10},
                               format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.get(f'/lessons/{video_lesson + 1}/stream/').status_code, 403)

    def test_reorder_moves_lessons_between_sections(self):
        teacher, slug, l1, l2 = self.build_course()
        self.as_user(teacher)
        course = Course.objects.get(slug=slug)
        s1 = course.sections.get()
        s2 = Section.objects.create(course=course, title='More', order=1)
        res = self.client.post(f'/courses/{slug}/reorder/', {'sections': [
            {'id': s1.id, 'lessons': [l2]}, {'id': s2.id, 'lessons': [l1]}]}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Lesson.objects.get(pk=l1).section_id, s2.id)

    def test_multipart_upload_uses_presigned_parts(self):
        self.as_user(self.register('teacher', 'mp'))
        fake = mock.Mock(name='s3', supports_multipart=True)
        fake.create_multipart.return_value = 'upload-1'
        fake.presign_part.side_effect = lambda key, uid, n: f'https://s3/{n}'
        fake.object_size.return_value = 200 * 1024 * 1024
        with mock.patch('uploads.views.get_storage', return_value=fake):
            res = self.client.post('/uploads/', {
                'kind': 'video', 'filename': 'big.mp4', 'content_type': 'video/mp4',
                'size': 200 * 1024 * 1024}, format='json')
            self.assertEqual(res.data['strategy'], 'multipart')
            self.assertEqual(res.data['part_count'], 13)
            asset = res.data['asset']['id']
            urls = self.client.post(f'/uploads/{asset}/parts/', {'part_numbers': [1, 2]},
                                    format='json').json()['urls']
            self.assertEqual(urls['1'], 'https://s3/1')
            done = self.client.post(f'/uploads/{asset}/complete/', {'parts': [
                {'part_number': 1, 'etag': '"a"'}, {'part_number': 2, 'etag': '"b"'}]},
                format='json')
            self.assertEqual(done.status_code, 200)
            fake.complete_multipart.assert_called_once()

    def test_seed_demo_populates_catalog(self):
        call_command('seed_demo', '--demo-users', stdout=mock.Mock())
        res = self.client.get('/courses/?ordering=rating&department=fine-arts').data
        self.assertEqual(res['count'], 2)
        self.assertGreater(res['results'][0]['lesson_count'], 0)
        login = self.client.post('/auth/login/', {'login': 'demo_student',
                                                  'password': 'learn-together-2026'},
                                 format='json')
        self.assertEqual(login.data['user']['role'], 'student')
        teachers = self.client.get('/teachers/').data
        self.assertEqual(len(teachers), 7)
        profile = self.client.get(f"/teachers/{teachers[0]['id']}/").data
        self.assertGreater(profile['stats']['courses'], 0)
        self.assertEqual(len(self.client.get('/departments/').data), 6)


class StreakTests(APITestCase):
    def test_streaks(self):
        today = timezone.localdate()
        days = [today - timedelta(days=n) for n in (0, 1, 2, 5, 6, 7, 8)]
        self.assertEqual(streaks(days), (3, 4))
        self.assertEqual(streaks([today - timedelta(days=3)]), (0, 1))
