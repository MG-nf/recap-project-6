from django.http import Http404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .ai_client import AIConfigurationError
from .models import Goal, LearningSession, Resource
from .serializers import (
    GoalDetailSerializer,
    GoalSerializer,
    LearningSessionSerializer,
    ResourceSerializer,
)
from .services import (
    AIServiceError,
    GoalNotOwnedError,
    InvalidGoalIdError,
    InvalidStatusError,
    NoSessionDataError,
    create_goal,
    create_resource,
    create_session,
    delete_goal,
    delete_resource,
    delete_session,
    generate_summary_for_goal,
    get_goal_for_user,
    get_resource_for_user,
    get_session_for_user,
    goals_for_user,
    list_goals_for_user,
    list_resources_for_user,
    list_sessions_for_user,
    resources_for_user,
    sessions_for_user,
    suggest_next_steps_for_goal,
    update_goal,
    update_resource,
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
    serializer_class = GoalDetailSerializer
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
        try:
            serializer.instance = update_session(
                serializer.instance, user=self.request.user, **serializer.validated_data
            )
        except GoalNotOwnedError as exc:
            raise ValidationError({"goal": [str(exc)]})

    def perform_destroy(self, instance):
        delete_session(instance)


class ResourceListCreateView(generics.ListCreateAPIView):
    serializer_class = ResourceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Base (unfiltered-by-goal) queryset used by the browsable API
        # renderer's filter form and OPTIONS metadata; actual GET responses
        # are served by list() below, which applies the goal filter.
        return resources_for_user(self.request.user)

    def list(self, request, *args, **kwargs):
        goal_id = request.query_params.get("goal")
        try:
            resources = list_resources_for_user(request.user, goal_id=goal_id)
        except InvalidGoalIdError as exc:
            return Response({"goal": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(resources, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        try:
            resource = create_resource(user=self.request.user, **serializer.validated_data)
        except GoalNotOwnedError as exc:
            raise ValidationError({"goal": [str(exc)]})
        serializer.instance = resource


class ResourceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ResourceSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        try:
            return get_resource_for_user(self.request.user, self.kwargs["pk"])
        except Resource.DoesNotExist:
            raise Http404

    def perform_update(self, serializer):
        try:
            serializer.instance = update_resource(
                serializer.instance, user=self.request.user, **serializer.validated_data
            )
        except GoalNotOwnedError as exc:
            raise ValidationError({"goal": [str(exc)]})

    def perform_destroy(self, instance):
        delete_resource(instance)


class GenerateSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            goal = get_goal_for_user(request.user, pk)
        except Goal.DoesNotExist:
            raise Http404
        try:
            summary = generate_summary_for_goal(goal)
        except NoSessionDataError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except AIConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except AIServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"summary": summary})


class SuggestNextStepsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            goal = get_goal_for_user(request.user, pk)
        except Goal.DoesNotExist:
            raise Http404
        try:
            steps = suggest_next_steps_for_goal(goal)
        except NoSessionDataError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except AIConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except AIServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"steps": steps})
