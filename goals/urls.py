from django.urls import path

from .views import (
    GenerateSummaryView,
    GoalDetailView,
    GoalListCreateView,
    LearningSessionDetailView,
    LearningSessionListCreateView,
    ResourceDetailView,
    ResourceListCreateView,
    SuggestNextStepsView,
)

urlpatterns = [
    path("goals/", GoalListCreateView.as_view(), name="goal-list"),
    path("goals/<int:pk>/", GoalDetailView.as_view(), name="goal-detail"),
    path(
        "goals/<int:pk>/generate-summary/",
        GenerateSummaryView.as_view(),
        name="goal-generate-summary",
    ),
    path(
        "goals/<int:pk>/suggest-next-steps/",
        SuggestNextStepsView.as_view(),
        name="goal-suggest-next-steps",
    ),
    path("sessions/", LearningSessionListCreateView.as_view(), name="session-list"),
    path("sessions/<int:pk>/", LearningSessionDetailView.as_view(), name="session-detail"),
    path("resources/", ResourceListCreateView.as_view(), name="resource-list"),
    path("resources/<int:pk>/", ResourceDetailView.as_view(), name="resource-detail"),
]
