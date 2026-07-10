from django.contrib.auth import login, logout
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, ProfileSerializer, SignUpSerializer
from .services import (
    InvalidCredentialsError,
    UsernameTakenError,
    authenticate_user,
    get_profile_for_user,
    register_user,
)
from .throttles import AuthRateThrottle


class SignUpView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]
    throttle_scope = 'signup'

    def post(self, request):
        serializer = SignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, profile = register_user(**serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({"password": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        except UsernameTakenError as exc:
            return Response({"username": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response(ProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = authenticate_user(**serializer.validated_data)
        except InvalidCredentialsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response(status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_200_OK)


class ProfileView(RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        try:
            return get_profile_for_user(self.request.user)
        except ObjectDoesNotExist:
            raise Http404
