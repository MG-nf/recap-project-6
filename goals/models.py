from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Goal(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in-progress", "In progress"
        DONE = "done", "Done"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="goals"
    )
    title = models.CharField(max_length=200)
    desc = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PLANNED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["user", "status"])]
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class LearningSession(models.Model):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="sessions")
    date = models.DateField()
    duration = models.PositiveIntegerField(
        help_text="Duration in minutes", validators=[MinValueValidator(1)]
    )
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.goal.title} — {self.date}"


class Resource(models.Model):
    class Type(models.TextChoices):
        ARTICLE = "article", "Article"
        VIDEO = "video", "Video"
        REPO = "repo", "Repo"
        DOC = "doc", "Doc"

    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="resources")
    title = models.CharField(max_length=200)
    url = models.URLField(max_length=500)
    type = models.CharField(max_length=20, choices=Type.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["goal", "type"])]
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
