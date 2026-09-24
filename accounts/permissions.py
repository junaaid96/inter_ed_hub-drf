from rest_framework.permissions import BasePermission


class IsTeacher(BasePermission):
    message = 'Only teachers can do this.'

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and hasattr(request.user, 'teacher'))


class IsStudent(BasePermission):
    message = 'Only students can do this.'

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and hasattr(request.user, 'student'))
