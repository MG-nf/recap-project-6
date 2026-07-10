from django.contrib.auth.models import User
from django.contrib.auth.validators import UnicodeUsernameValidator
from rest_framework import serializers

from .models import FocusArea, Profile


class FocusAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = FocusArea
        fields = ["id", "name"]


class ProfileSerializer(serializers.ModelSerializer):
    focus_area = FocusAreaSerializer(many=True, read_only=True)

    class Meta:
        model = Profile
        fields = ["name", "cohort", "focus_area"]


class SignUpSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
    password = serializers.CharField(write_only=True)
    name = serializers.CharField()
    cohort = serializers.CharField()
    focus_area = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_focus_area(self, value):
        existing = set(FocusArea.objects.filter(name__in=value).values_list("name", flat=True))
        unknown = set(value) - existing
        if unknown:
            raise serializers.ValidationError(f"Unknown focus area(s): {', '.join(sorted(unknown))}")
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
