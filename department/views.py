from django.shortcuts import render
from rest_framework.generics import ListAPIView
from .models import Department
from .serializers import DepartmentSerializer

# Create your views here.


class DepartmentList(ListAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
