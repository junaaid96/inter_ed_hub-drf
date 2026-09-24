from rest_framework import serializers

from .models import Department


class DepartmentSerializer(serializers.ModelSerializer):
    course_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Department
        fields = ['id', 'name', 'slug', 'description', 'icon', 'course_count']
