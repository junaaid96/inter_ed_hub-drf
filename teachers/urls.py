from django.urls import path
from .views import TeacherListView, TeacherRegistrationView, TeacherLoginView, TeacherLogoutView, TeacherUpdateView, TeacherDetailView

urlpatterns = [
    path('', TeacherListView.as_view(), name='teacher_list'),
    path('<int:pk>/', TeacherDetailView.as_view(), name='teacher_detail'),
    path('register/', TeacherRegistrationView.as_view(),
         name='teacher_registration'),
    path('activate/<uid64>/<token>/',
         TeacherRegistrationView.activate_account, name='teacher_activation'),
    path('login/', TeacherLoginView.as_view(), name='teacher_login'),
    path('logout/', TeacherLogoutView.as_view(), name='teacher_logout'),
    path('update/', TeacherUpdateView.as_view(), name='teacher_update'),
]
