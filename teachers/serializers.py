from rest_framework import serializers
from .models import Teacher
from django.contrib.auth.models import User
from django.contrib.auth import authenticate


class TeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = '__all__'


class RegistrationSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    # write_only = True means that the field will be used when creating an instance of the model, but it won't be included when serializing the model instance.
    confirm_password = serializers.CharField(write_only=True)

    profile_pic = serializers.ImageField(required=False)
    bio = serializers.CharField()
    designation = serializers.CharField()
    department = serializers.CharField()
    phone = serializers.CharField()

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password',
                  'confirm_password', 'profile_pic', 'bio', 'designation', 'department', 'phone')
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate(self, data):
        password = data.get('password')
        confirm_password = data.pop('confirm_password')

        if password != confirm_password:
            raise serializers.ValidationError('Passwords must match!')

        return data

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email is already taken!')
        return value

    def create(self, validated_data):
        profile_pic = validated_data.pop('profile_pic', None)
        bio = validated_data.pop('bio')
        designation = validated_data.pop('designation')
        department = validated_data.pop('department')
        phone = validated_data.pop('phone')

        user = User.objects.create_user(
            username=validated_data['username'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            email=validated_data['email'],
            password=validated_data['password']
        )

        user.is_active = False
        user.save()

        teacher = Teacher.objects.create(
            user=user,
            profile_pic=profile_pic,
            bio=bio,
            designation=designation,
            department=department,
            phone=phone
        )

        return user


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class UserUpdateSerializer(serializers.ModelSerializer):
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    profile_pic = serializers.ImageField(required=False)
    bio = serializers.CharField()
    designation = serializers.CharField()
    department = serializers.CharField()
    phone = serializers.CharField()

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email',
                  'profile_pic', 'bio', 'designation', 'department', 'phone')
        extra_kwargs = {
            'username': {'read_only': True},
            'email': {'read_only': True}
        }

    def update(self, instance, validated_data):
        instance.first_name = validated_data.get(
            'first_name', instance.first_name)
        instance.last_name = validated_data.get(
            'last_name', instance.last_name)
        instance.save()

        teacher = instance.teacher
        teacher.profile_pic = validated_data.get(
            'profile_pic', teacher.profile_pic)
        teacher.bio = validated_data.get('bio', teacher.bio)
        teacher.designation = validated_data.get(
            'designation', teacher.designation)
        teacher.department = validated_data.get(
            'department', teacher.department)
        teacher.phone = validated_data.get('phone', teacher.phone)
        teacher.save()

        return instance
