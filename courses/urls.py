from django.urls import path

from . import views

urlpatterns = [
    # Catalog
    path('courses/', views.CourseListCreateView.as_view(), name='course-list'),
    path('courses/<slug:slug>/', views.CourseDetailView.as_view(), name='course-detail'),
    path('courses/<slug:slug>/enroll/', views.EnrollView.as_view(), name='course-enroll'),
    path('courses/<slug:slug>/reviews/', views.ReviewListCreateView.as_view(), name='course-reviews'),
    path('courses/<slug:slug>/notes/', views.CourseNotesView.as_view(), name='course-notes'),
    path('courses/<slug:slug>/sections/', views.SectionCreateView.as_view(), name='section-create'),
    path('courses/<slug:slug>/reorder/', views.ReorderView.as_view(), name='course-reorder'),
    # Studio
    path('studio/courses/', views.StudioCourseListView.as_view(), name='studio-courses'),
    path('studio/courses/<slug:slug>/', views.StudioCourseDetailView.as_view(), name='studio-course'),
    path('sections/<int:pk>/', views.SectionDetailView.as_view(), name='section-detail'),
    path('sections/<int:pk>/lessons/', views.LessonCreateView.as_view(), name='lesson-create'),
    # Learning
    path('lessons/<int:pk>/', views.LessonDetailView.as_view(), name='lesson-detail'),
    path('lessons/<int:pk>/stream/', views.LessonStreamView.as_view(), name='lesson-stream'),
    path('lessons/<int:pk>/progress/', views.LessonProgressView.as_view(), name='lesson-progress'),
    path('lessons/<int:pk>/notes/', views.NoteListCreateView.as_view(), name='lesson-notes'),
    path('lessons/<int:pk>/comments/', views.CommentListCreateView.as_view(), name='lesson-comments'),
    path('notes/<int:pk>/', views.NoteDetailView.as_view(), name='note-detail'),
    path('comments/<int:pk>/', views.CommentDetailView.as_view(), name='comment-detail'),
    # Dashboards
    path('me/learning/', views.MyLearningView.as_view(), name='my-learning'),
    path('me/teaching/', views.MyTeachingView.as_view(), name='my-teaching'),
    path('certificates/<str:code>/', views.CertificateView.as_view(), name='certificate'),
]
