import json
from rest_framework.response import Response
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate, login, logout
from .models import Student
from django.contrib.auth.models import User
from .serializers import StudentSerializer, StudentRegisterSerializer, StudentLoginSerializer, StudentUpdateSerializer
from rest_framework.authtoken.models import Token
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from rest_framework import status
from django.core.serializers import serialize
from urllib.parse import urljoin
from rest_framework.renderers import JSONRenderer
from rest_framework.decorators import api_view
from django.http import HttpResponse


class StudentListView(ListAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer


class StudentDetailView(RetrieveAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer


class StudentRegistrationView(APIView):
    serializer_class = StudentRegisterSerializer
    renderer_classes = [JSONRenderer]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            token = Token.objects.create(user=user)
            print("token: ", token.key)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            print("uid: ", uid)

            confirmation_url = f"https://inter-ed-hub-drf.onrender.com/students/activate/{uid}/{token.key}"

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

    @api_view(['GET'])
    def activate_account(request, uid64, token):
        try:
            uid = urlsafe_base64_decode(uid64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and Token.objects.get(user=user).key == token:
            user.is_active = True
            user.save()
            return HttpResponse('Account activated successfully! Please <a href="https://inter-ed-hub-nextjs.vercel.app/student/login">Login</a>', status=200)
        else:
            return Response({'message': 'Activation link is invalid!'}, status=400)


class StudentUpdateView(APIView):
    serializer_class = StudentUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            student = request.user.student
        except Student.DoesNotExist:
            raise Response({'message': 'You are not a student.'},
                           status=status.HTTP_400_BAD_REQUEST)

        data = {
            'username': request.user.username,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'profile_pic': student.profile_pic,
            'bio': student.bio,
            'department': student.department.pk,
            'phone': student.phone
        }

        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        try:
            student = request.user.student
        except Student.DoesNotExist:
            raise Response({'message': 'You are not a student.'},
                           status=status.HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(
            instance=student, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentLoginView(APIView):
    serializer_class = StudentLoginSerializer

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

                base_url = "https://inter-ed-hub-drf.onrender.com/media/"
                profile_pic_url = urljoin(base_url, str(
                    authenticated_user.student.profile_pic))

                department = serialize(
                    'json', [authenticated_user.student.department], fields=('name'))
                data = json.loads(department)

                custom_token_payload = {
                    'key': token.key,
                    'student_id': authenticated_user.student.id,
                    'username': authenticated_user.username,
                    'email': authenticated_user.email,
                    'first_name': authenticated_user.first_name,
                    'last_name': authenticated_user.last_name,
                    'profile_pic': profile_pic_url,
                    'bio': authenticated_user.student.bio,
                    'department': data[0]["fields"]["name"],
                    'phone': authenticated_user.student.phone,
                    'user_type': authenticated_user.student.user_type
                }

                return Response({'message': 'User logged in successfully!', 'token': custom_token_payload}, status=status.HTTP_200_OK)
            else:
                return Response({'message': 'Invalid credentials!'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentLogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({'message': 'User logged out successfully!'}, status=200)
