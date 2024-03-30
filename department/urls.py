from django.urls import path
from .views import DepartmentList

urlpatterns = [
    path('', DepartmentList.as_view(), name='department-list')
]
