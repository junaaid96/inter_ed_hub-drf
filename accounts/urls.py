from django.urls import path

from . import views

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/activate/', views.ActivateView.as_view(), name='activate'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('auth/password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('teachers/', views.TeacherListView.as_view(), name='teacher-list'),
    path('teachers/<int:pk>/', views.TeacherDetailView.as_view(), name='teacher-detail'),
]
