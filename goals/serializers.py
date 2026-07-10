from rest_framework import serializers

from .models import Goal, LearningSession


class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = ["id", "title", "desc", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class LearningSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningSession
        fields = ["id", "goal", "date", "duration", "notes", "tags"]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None:
            # Scope the choices to the caller's own goals so an existing-but-foreign
            # id and a nonexistent id produce the same generic "does not exist"
            # error, instead of leaking which goal ids belong to other users.
            self.fields["goal"].queryset = Goal.objects.filter(user=request.user)

    def validate_tags(self, value):
        if not isinstance(value, list) or not all(isinstance(tag, str) for tag in value):
            raise serializers.ValidationError("Tags must be a list of strings.")
        return value
