from django.contrib import admin

from .models import Goal, LearningSession, Resource

admin.site.register(Goal)
admin.site.register(LearningSession)
admin.site.register(Resource)
