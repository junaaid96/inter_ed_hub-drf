from django.urls import path
from .views import StudentListView, StudentRegistrationView, StudentUpdateView, StudentDetailView, StudentLoginView, StudentLogoutView

urlpatterns = [
    path('', StudentListView.as_view(), name='student_list'),
    path('<int:pk>/', StudentDetailView.as_view(), name='student_detail'),
    path('register/', StudentRegistrationView.as_view(),
         name='student_registration'),
    path('activate/<uid64>/<token>/',
         StudentRegistrationView.activate_account, name='student_activation'),
    path('login/', StudentLoginView.as_view(), name='student_login'),
    path('logout/', StudentLogoutView.as_view(), name='student_logout'),
    path('update/', StudentUpdateView.as_view(), name='student_update'),
]
