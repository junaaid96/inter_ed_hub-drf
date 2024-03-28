from rest_framework.response import Response
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound
from django.contrib.auth import authenticate, login, logout
from .models import Teacher
from django.contrib.auth.models import User
from .serializers import TeacherSerializer, RegistrationSerializer, UserLoginSerializer, UserUpdateSerializer
from rest_framework.authtoken.models import Token
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from rest_framework import status
from django.core.serializers import serialize


class TeacherListView(ListAPIView):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer


class TeacherDetailView(RetrieveAPIView):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer


class UserRegistrationView(APIView):
    serializer_class = RegistrationSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            token = Token.objects.create(user=user)
            print("token: ", token.key)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            print("uid: ", uid)

            confirmation_url = f"https://inter-ed-hub-drf.onrender.com/teachers/activate/{uid}/{token.key}"

            mail_subject = "Activate your account!"
            mail_body = render_to_string('activation_email.html', {
                'user': user,
                'confirmation_url': confirmation_url
            })
            email = EmailMultiAlternatives(
                mail_subject, '', to=[user.email])
            email.attach_alternative(mail_body, "text/html")
            email.send()

            return Response({'message': 'User registered. Check your email to activate!'}, status=201)

        return Response(serializer.errors, status=400)

    def activate_account(request, uid64, token):
        try:
            uid = urlsafe_base64_decode(uid64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and token == Token.objects.get(user=user).key:
            user.is_active = True
            user.save()
            return redirect('teacher_login')
        return Response({'message': 'Invalid activation link!'}, status=400)


class UserUpdateView(APIView):
    serializer_class = UserUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            teacher = request.user.teacher
        except Teacher.DoesNotExist:
            raise NotFound('You are not a teacher.')

        data = {
            'username': request.user.username,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'profile_pic': teacher.profile_pic,
            'bio': teacher.bio,
            'designation': teacher.designation,
            'department': teacher.department,
            'phone': teacher.phone
        }

        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=200)

    def put(self, request):
        serializer = self.serializer_class(
            instance=request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)


class UserLoginView(APIView):
    serializer_class = UserLoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data.get('username')
            password = serializer.validated_data.get('password')
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return Response({'message': 'User not found!'}, status=status.HTTP_400_BAD_REQUEST)

            if not user.is_active:
                return Response({'message': 'Please activate your account before login!'}, status=status.HTTP_400_BAD_REQUEST)

            authenticated_user = authenticate(
                username=username, password=password)

            if authenticated_user:
                login(request, authenticated_user)

                token, created = Token.objects.get_or_create(
                    user=authenticated_user)

                profile_pic = str(authenticated_user.teacher.profile_pic)

                custom_token_payload = {
                    'key': token.key,
                    'user_id': authenticated_user.id,
                    'username': authenticated_user.username,
                    'email': authenticated_user.email,
                    'first_name': authenticated_user.first_name,
                    'last_name': authenticated_user.last_name,
                    'profile_pic': profile_pic,
                    'bio': authenticated_user.teacher.bio,
                    'designation': authenticated_user.teacher.designation,
                    'department': authenticated_user.teacher.department,
                    'phone': authenticated_user.teacher.phone
                }

                return Response({'message': 'User logged in successfully!', 'token': custom_token_payload}, status=status.HTTP_200_OK)
            else:
                return Response({'message': 'Invalid credentials!'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({'message': 'User logged out successfully!'}, status=200)
