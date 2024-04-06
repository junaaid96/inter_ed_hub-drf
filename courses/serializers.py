from rest_framework.serializers import ModelSerializer, StringRelatedField
from .models import Course


class CourseSerializer(ModelSerializer):
    teacher = StringRelatedField()
    department = StringRelatedField()
    enrolled_students = StringRelatedField(many=True)

    class Meta:
        model = Course
        fields = '__all__'


class CourseCreateSerializer(ModelSerializer):
    class Meta:
        model = Course
        fields = ['title', 'description', 'duration',
                  'credit', 'department', 'image']
