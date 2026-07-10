from django.conf import settings
from django.db import models


class FocusArea(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    name = models.CharField(max_length=150)
    cohort = models.CharField(max_length=100)
    focus_area = models.ManyToManyField(FocusArea, related_name="profiles", blank=True)

    def __str__(self):
        return self.name
