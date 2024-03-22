from django.urls import path
from .views import TeacherListView, UserRegistrationView, UserLoginView, UserLogoutView, UserUpdateView, TeacherDetailView

urlpatterns = [
    path('', TeacherListView.as_view(), name='teacher_list'),
    path('<int:pk>/', TeacherDetailView.as_view(), name='teacher_detail'),
    path('register/', UserRegistrationView.as_view(), name='teacher_registration'),
    path('activate/<uid64>/<token>/', UserRegistrationView.activate_account, name='teacher_activation'),
    path('login/', UserLoginView.as_view(), name='teacher_login'),
    path('logout/', UserLogoutView.as_view(), name='teacher_logout'),
    path('update/', UserUpdateView.as_view(), name='teacher_update'),
]
