from django.db.models import Count, Q
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from .models import Department
from .serializers import DepartmentSerializer


class DepartmentList(ListAPIView):
    serializer_class = DepartmentSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return Department.objects.annotate(
            course_count=Count('course', filter=Q(course__is_published=True)))
