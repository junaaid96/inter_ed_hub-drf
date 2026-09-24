from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from teachers.models import Teacher

from .serializers import LoginSerializer, MeSerializer, PersonSerializer, RegisterSerializer


class AuthThrottleMixin:
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'


def auth_payload(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'token': token.key, 'user': MeSerializer(user).data}


def send_activation_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f'{settings.FRONTEND_URL}/activate?uid={uid}&token={token}'
    send_mail(
        'Confirm your InterEd Hub account',
        f'Hi {user.first_name},\n\nConfirm your email to start learning:\n{link}\n\n'
        'If you did not sign up, you can ignore this message.\n\nThe InterEd Hub team',
        None, [user.email],
    )


class RegisterView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        needs_activation = settings.REQUIRE_EMAIL_ACTIVATION
        serializer = RegisterSerializer(data=request.data,
                                        context={'active': not needs_activation})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        if needs_activation:
            send_activation_email(user)
            return Response({'activation_required': True,
                             'detail': 'Check your inbox to confirm your email.'},
                            status=status.HTTP_201_CREATED)
        return Response(auth_payload(user), status=status.HTTP_201_CREATED)


class ActivateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            uid = force_str(urlsafe_base64_decode(request.data.get('uid', '')))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        if user is None or not default_token_generator.check_token(
                user, request.data.get('token', '')):
            return Response({'detail': 'This activation link is invalid or expired.'},
                            status=status.HTTP_400_BAD_REQUEST)
        user.is_active = True
        user.save(update_fields=['is_active'])
        return Response(auth_payload(user))


class LoginView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        login = serializer.validated_data['login'].strip()
        password = serializer.validated_data['password']

        candidate = User.objects.filter(Q(username__iexact=login) | Q(email__iexact=login)).first()
        if candidate and not candidate.is_active and candidate.check_password(password):
            return Response({'detail': 'Please confirm your email before signing in.'},
                            status=status.HTTP_403_FORBIDDEN)
        user = authenticate(request, username=candidate.username if candidate else login,
                            password=password)
        if user is None:
            return Response({'detail': 'Incorrect username/email or password.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(auth_payload(user))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)

    def patch(self, request):
        serializer = MeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MeSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError

        user = request.user
        if not user.check_password(request.data.get('current_password', '')):
            return Response({'current_password': ['Current password is incorrect.']}, status=400)
        new = request.data.get('new_password', '')
        try:
            validate_password(new, user)
        except ValidationError as exc:
            return Response({'new_password': list(exc.messages)}, status=400)
        user.set_password(new)
        user.save()
        Token.objects.filter(user=user).delete()
        return Response(auth_payload(user))


class TeacherListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        teachers = (Teacher.objects.select_related('user', 'avatar', 'department')
                    .annotate(course_count=Count('courses', filter=Q(courses__is_published=True),
                                                 distinct=True),
                              student_count=Count('courses__enrollments', distinct=True))
                    .order_by('-student_count', 'user__first_name'))
        return Response([
            {**PersonSerializer(t).data,
             'department': t.department.name if t.department else None,
             'course_count': t.course_count, 'student_count': t.student_count}
            for t in teachers
        ])


class TeacherDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        from courses.serializers import CourseCardSerializer, annotate_course_stats

        teacher = get_object_or_404(Teacher.objects.select_related('user', 'avatar', 'department'),
                                    pk=pk)
        courses = annotate_course_stats(teacher.courses.filter(is_published=True))
        stats = courses.aggregate(students=Count('enrollments', distinct=True),
                                  rating=Avg('reviews__rating'),
                                  reviews=Count('reviews', distinct=True))
        return Response({
            **PersonSerializer(teacher).data,
            'bio': teacher.bio,
            'website': teacher.website,
            'department': teacher.department.name if teacher.department else None,
            'joined': teacher.created_at,
            'stats': {'courses': courses.count(), 'students': stats['students'],
                      'rating': round(stats['rating'] or 0, 2), 'reviews': stats['reviews']},
            'courses': CourseCardSerializer(courses, many=True,
                                            context={'request': request}).data,
        })
