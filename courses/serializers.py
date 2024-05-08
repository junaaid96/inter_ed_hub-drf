from rest_framework.serializers import ModelSerializer, StringRelatedField
from .models import Course, CourseProgress


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


class CourseProgressSerializer(ModelSerializer):
    # course = StringRelatedField()
    # student = StringRelatedField()

    class Meta:
        model = CourseProgress
        fields = '__all__'
