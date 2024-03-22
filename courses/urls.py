from django.urls import path
from .views import CourseListView, CourseDetailView, CourseCreateView, CourseUpdateView, CourseDeleteView

urlpatterns = [
    path('', CourseListView.as_view(), name='course-list'),
    path('<pk>', CourseDetailView.as_view(), name='course-details'),
    path('create/', CourseCreateView.as_view(), name='course-create'),
    path('<pk>/update/', CourseUpdateView.as_view(), name='course-update'),
    path('<pk>/delete/', CourseDeleteView.as_view(), name='course-delete'),
]
