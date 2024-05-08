from django.urls import path
from .views import CourseListView, CourseDetailView, CourseCreateView, CourseUpdateView, CourseDeleteView, CourseEnrollView, CourseProgressView

urlpatterns = [
    path('', CourseListView.as_view(), name='course-list'),
    path('<int:pk>/', CourseDetailView.as_view(), name='course-details'),
    path('create/', CourseCreateView.as_view(), name='course-create'),
    path('<int:pk>/progress/', CourseProgressView.as_view(), name='course-progress'),
    path('<int:pk>/update/', CourseUpdateView.as_view(), name='course-update'),
    path('<int:pk>/delete/', CourseDeleteView.as_view(), name='course-delete'),
    path('<int:pk>/enroll/', CourseEnrollView.as_view(), name='course-enroll'),
]
