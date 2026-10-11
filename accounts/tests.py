

from django.core.management import call_command as _call
from django.test import override_settings as _ovr
from rest_framework.test import APITestCase as _APITC


@_ovr(REQUIRE_EMAIL_ACTIVATION=False)
class DemoAccountTests(_APITC):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)
        _call('seed_demo', '--demo-users', verbosity=0)
        _call('seed_demo', '--demo-users', verbosity=0)  # idempotent

    def login(self, username):
        from accounts.demo import DEMO_PASSWORD
        res = self.client.post('/auth/login/', {'login': username, 'password': DEMO_PASSWORD}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + res.data['token'])
        return res.data['user']

    def test_both_roles_log_in(self):
        self.assertEqual(self.login('demo_teacher')['role'], 'teacher')
        self.client.credentials()
        self.assertEqual(self.login('demo_student')['role'], 'student')

    def test_demo_cannot_change_credentials(self):
        self.login('demo_student')
        self.assertEqual(self.client.patch('/auth/me/', {'email': 'x@y.com'}, format='json').status_code, 403)
        self.assertEqual(self.client.post('/auth/password/', {'current_password': 'learn-together-2026', 'new_password': 'Zz9!long-enough'}, format='json').status_code, 403)
        self.assertEqual(self.client.patch('/auth/me/', {'bio': 'hi'}, format='json').status_code, 200)
