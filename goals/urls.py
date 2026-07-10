from django.urls import path

from .views import (
    GoalDetailView,
    GoalListCreateView,
    LearningSessionDetailView,
    LearningSessionListCreateView,
    ResourceDetailView,
    ResourceListCreateView,
)

urlpatterns = [
    path("goals/", GoalListCreateView.as_view(), name="goal-list"),
    path("goals/<int:pk>/", GoalDetailView.as_view(), name="goal-detail"),
    path("sessions/", LearningSessionListCreateView.as_view(), name="session-list"),
    path("sessions/<int:pk>/", LearningSessionDetailView.as_view(), name="session-detail"),
    path("resources/", ResourceListCreateView.as_view(), name="resource-list"),
    path("resources/<int:pk>/", ResourceDetailView.as_view(), name="resource-detail"),
]
