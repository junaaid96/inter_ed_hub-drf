from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from department.models import Department
from students.models import Student
from teachers.models import Teacher
from uploads.models import MediaAsset


def profile_of(user):
    for attr in ('teacher', 'student'):
        profile = getattr(user, attr, None) if user and user.is_authenticated else None
        if profile is not None:
            return profile
    return None


def avatar_url(profile):
    if profile and profile.avatar_id and profile.avatar.is_ready:
        return profile.avatar.public_url()
    return None


class PersonSerializer(serializers.Serializer):
    """Compact public representation of a teacher or student."""

    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    headline = serializers.SerializerMethodField()

    def get_name(self, profile):
        return str(profile)

    def get_avatar(self, profile):
        return avatar_url(profile)

    def get_headline(self, profile):
        return getattr(profile, 'designation', '') or ''


class MeSerializer(serializers.Serializer):
    """The signed-in user's own account + profile, readable and writable."""

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, allow_blank=True)
    role = serializers.SerializerMethodField()
    profile_id = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    avatar_id = serializers.PrimaryKeyRelatedField(
        queryset=MediaAsset.objects.filter(kind=MediaAsset.Kind.IMAGE), required=False,
        allow_null=True, write_only=True)
    bio = serializers.CharField(allow_blank=True, required=False)
    phone = serializers.CharField(allow_blank=True, required=False, max_length=20)
    designation = serializers.CharField(allow_blank=True, required=False, max_length=100)
    website = serializers.URLField(allow_blank=True, required=False)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True)
    department_name = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField(read_only=True)

    def get_role(self, user):
        profile = profile_of(user)
        return profile.role if profile else ('admin' if user.is_staff else None)

    def get_profile_id(self, user):
        profile = profile_of(user)
        return profile.pk if profile else None

    def get_avatar(self, user):
        return avatar_url(profile_of(user))

    def get_department_name(self, user):
        profile = profile_of(user)
        return profile.department.name if profile and profile.department else None

    def to_representation(self, user):
        data = super().to_representation(user)
        profile = profile_of(user)
        for field in ('bio', 'phone', 'designation', 'website'):
            data[field] = getattr(profile, field, '') if profile else ''
        data['department'] = profile.department_id if profile else None
        return data

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('That username is taken.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('That email is already registered.')
        return value

    def validate_avatar_id(self, asset):
        if asset and (asset.owner_id != self.instance.pk or not asset.is_ready):
            raise serializers.ValidationError('Upload the image first.')
        return asset

    @transaction.atomic
    def update(self, user, data):
        for field in ('username', 'email', 'first_name', 'last_name'):
            if field in data:
                setattr(user, field, data[field])
        user.save()
        profile = profile_of(user)
        if profile:
            if 'avatar_id' in data:
                profile.avatar = data['avatar_id']
            for field in ('bio', 'phone', 'department', 'designation', 'website'):
                if field in data and hasattr(profile, field):
                    setattr(profile, field, data[field])
            profile.save()
        return user


class RegisterSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['student', 'teacher'])
    username = serializers.RegexField(r'^[\w.@+-]+$', max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True)
    designation = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('That username is taken.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('That email is already registered.')
        return value.lower()

    def validate(self, data):
        user = User(username=data['username'], email=data['email'],
                    first_name=data['first_name'], last_name=data.get('last_name', ''))
        validate_password(data['password'], user)
        return data

    @transaction.atomic
    def create(self, data):
        user = User.objects.create_user(
            username=data['username'], email=data['email'], password=data['password'],
            first_name=data['first_name'], last_name=data.get('last_name', ''),
            is_active=self.context.get('active', True),
        )
        if data['role'] == 'teacher':
            Teacher.objects.create(user=user, department=data.get('department'),
                                   designation=data.get('designation', ''))
        else:
            Student.objects.create(user=user, department=data.get('department'))
        return user


class LoginSerializer(serializers.Serializer):
    login = serializers.CharField(help_text='Username or email')
    password = serializers.CharField(style={'input_type': 'password'})
