from django.contrib import admin

from .models import Goal, LearningSession

admin.site.register(Goal)
admin.site.register(LearningSession)
