from rest_framework import serializers
from .models import Teacher
from department.models import Department
from django.contrib.auth.models import User
from django.contrib.auth import authenticate


class TeacherSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    first_name = serializers.CharField(
        source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    department = serializers.StringRelatedField()

    class Meta:
        model = Teacher
        fields = 'id', 'username', 'first_name', 'last_name', 'email', 'profile_pic', 'bio', 'designation', 'department', 'phone'


class RegistrationSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    # write_only = True means that the field will be used when creating an instance of the model, but it won't be included when serializing the model instance.
    confirm_password = serializers.CharField(write_only=True)

    profile_pic = serializers.ImageField(required=False)
    bio = serializers.CharField()
    designation = serializers.CharField()
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all()
    )
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
    username = serializers.CharField(
        source='user.username')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    email = serializers.EmailField(source='user.email')

    profile_pic = serializers.ImageField(required=False)
    bio = serializers.CharField()
    designation = serializers.CharField()
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all()
    )
    phone = serializers.CharField()

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email',
                  'profile_pic', 'bio', 'designation', 'department', 'phone')

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user = instance.user
            user.username = user_data.get('username', user.username)
            user.first_name = user_data.get('first_name', user.first_name)
            user.last_name = user_data.get('last_name', user.last_name)
            user.email = user_data.get('email', user.email)
            user.save()

        instance.profile_pic = validated_data.get(
            'profile_pic', instance.profile_pic)
        instance.bio = validated_data.get('bio', instance.bio)
        instance.designation = validated_data.get(
            'designation', instance.designation)
        instance.department = validated_data.get(
            'department', instance.department)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.save()

        return instance
