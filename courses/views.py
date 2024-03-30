from rest_framework.generics import ListAPIView, RetrieveAPIView, DestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from .models import Course
from .serializers import CourseSerializer, CourseCreateSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import pagination, filters


class CoursePagination(pagination.PageNumberPagination):
    page_size = 6
    page_query_param = 'page_size'
    max_page_size = 60


class CourseListView(ListAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    pagination_class = CoursePagination
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'department',
                     'teacher__user__first_name', 'teacher__user__last_name']

    def get_queryset(self):
        queryset = Course.objects.all()
        department = self.request.query_params.get('department')
        teacher = self.request.query_params.get('teacher')

        if department:
            queryset = queryset.filter(department=department)
        if teacher:
            queryset = queryset.filter(teacher__user__username=teacher)

        return queryset


class CourseDetailView(RetrieveAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer


class CourseCreateView(APIView):
    serializer_class = CourseCreateSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save(teacher=request.user.teacher)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CourseUpdateView(APIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        course = Course.objects.get(pk=pk)
        serializer = CourseSerializer(course)
        return Response(serializer.data)

    def put(self, request, pk):
        course = Course.objects.get(pk=pk)
        if request.user.teacher == course.teacher:
            serializer = CourseSerializer(course, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            raise PermissionDenied(
                "You do not have permission to update this course.")


class CourseDeleteView(DestroyAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        if self.request.user.teacher == instance.teacher:
            instance.delete()
        else:
            raise PermissionDenied(
                "You do not have permission to delete this course.")
