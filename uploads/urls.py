from django.urls import path

from . import views

urlpatterns = [
    path('', views.UploadInitView.as_view(), name='upload-init'),
    path('<uuid:pk>/parts/', views.UploadPartsView.as_view(), name='upload-parts'),
    path('<uuid:pk>/complete/', views.UploadCompleteView.as_view(), name='upload-complete'),
    path('<uuid:pk>/abort/', views.UploadAbortView.as_view(), name='upload-abort'),
    path('local/put/', views.local_object_put, name='local-object-put'),
    path('local/get/', views.local_object_get, name='local-object-get'),
]
