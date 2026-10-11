"""Public demo accounts behind the "Explore the demo" buttons on the login page.

The password is public on purpose; these accounts can't change their
username, email or password.
"""

DEMO_PASSWORD = 'learn-together-2026'
DEMO_USERNAMES = {'demo_teacher', 'demo_student'}


def is_demo(user):
    return bool(getattr(user, 'is_authenticated', False)) and user.username in DEMO_USERNAMES
