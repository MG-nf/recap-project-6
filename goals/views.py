from django.http import Http404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Goal, LearningSession
from .serializers import GoalSerializer, LearningSessionSerializer
from .services import (
    GoalNotOwnedError,
    InvalidGoalIdError,
    InvalidStatusError,
    create_goal,
    create_session,
    delete_goal,
    delete_session,
    get_goal_for_user,
    get_session_for_user,
    goals_for_user,
    list_goals_for_user,
    list_sessions_for_user,
    sessions_for_user,
    update_goal,
    update_session,
)


class GoalListCreateView(generics.ListCreateAPIView):
    serializer_class = GoalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Base (unfiltered-by-status) queryset used by the browsable API
        # renderer's filter form and OPTIONS metadata; actual GET responses
        # are served by list() below, which applies the status filter.
        return goals_for_user(self.request.user)

    def list(self, request, *args, **kwargs):
        status_param = request.query_params.get("status")
        try:
            goals = list_goals_for_user(request.user, status=status_param)
        except InvalidStatusError as exc:
            return Response({"status": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(goals, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        goal = create_goal(user=self.request.user, **serializer.validated_data)
        serializer.instance = goal


class GoalDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = GoalSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        try:
            return get_goal_for_user(self.request.user, self.kwargs["pk"])
        except Goal.DoesNotExist:
            raise Http404

    def perform_update(self, serializer):
        serializer.instance = update_goal(serializer.instance, **serializer.validated_data)

    def perform_destroy(self, instance):
        delete_goal(instance)


class LearningSessionListCreateView(generics.ListCreateAPIView):
    serializer_class = LearningSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Base (unfiltered-by-goal) queryset used by the browsable API
        # renderer's filter form and OPTIONS metadata; actual GET responses
        # are served by list() below, which applies the goal filter.
        return sessions_for_user(self.request.user)

    def list(self, request, *args, **kwargs):
        goal_id = request.query_params.get("goal")
        try:
            sessions = list_sessions_for_user(request.user, goal_id=goal_id)
        except InvalidGoalIdError as exc:
            return Response({"goal": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(sessions, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        try:
            session = create_session(user=self.request.user, **serializer.validated_data)
        except GoalNotOwnedError as exc:
            raise ValidationError({"goal": [str(exc)]})
        serializer.instance = session


class LearningSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LearningSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        try:
            return get_session_for_user(self.request.user, self.kwargs["pk"])
        except LearningSession.DoesNotExist:
            raise Http404

    def perform_update(self, serializer):
        serializer.instance = update_session(serializer.instance, **serializer.validated_data)

    def perform_destroy(self, instance):
        delete_session(instance)
