from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from uploads.views import media_redirect


def root_view(request):
    return JsonResponse({'name': 'InterEd Hub API', 'status': 'ok'})


urlpatterns = [
    path('', root_view, name='root'),
    path('admin/', admin.site.urls),
    path('departments/', include('department.urls')),
    path('uploads/', include('uploads.urls')),
    path('media/<uuid:pk>/', media_redirect, name='media'),
    path('', include('accounts.urls')),
    path('', include('courses.urls')),
]
