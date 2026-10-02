from django.contrib.auth import authenticate
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from config.throttles import AuthThrottle

from .serializers import LoginSerializer, RefreshSerializer, SignupSerializer, UserSerializer


def make_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


@extend_schema(request=SignupSerializer, responses={201: OpenApiTypes.OBJECT})
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def signup(request):
    serializer = SignupSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.save()
    tokens = make_tokens(user)
    return Response(
        {
            "user": UserSerializer(user).data,
            "access": tokens["access"],
            "refresh": tokens["refresh"],
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(request=LoginSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(
        request,
        email=serializer.validated_data["email"],
        password=serializer.validated_data["password"],
    )
    if user is None:
        # Same message for unknown email and wrong password, so this endpoint
        # can't be used to find out which emails are registered.
        return Response(
            {"detail": "Incorrect email or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    return Response(make_tokens(user))


@extend_schema(request=RefreshSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def refresh_token(request):
    serializer = RefreshSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        refresh = RefreshToken(serializer.validated_data["refresh"])
    except TokenError:
        return Response(
            {"detail": "Refresh token is invalid or expired."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    return Response({"access": str(refresh.access_token)})


@extend_schema(responses=UserSerializer)
@api_view(["GET"])
def me(request):
    return Response(UserSerializer(request.user).data)
