from django.contrib.auth import get_user_model, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetLinkSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .tasks import send_password_reset_email

User = get_user_model()


class AuthThrottleMixin:
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class CsrfTokenView(APIView):
    """Sets the `csrftoken` cookie; clients send it back in `X-CSRFToken`."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


# DRF marks every APIView as csrf_exempt and only enforces CSRF for
# *authenticated* session users. Login/register are called by anonymous
# users, so we enforce CSRF explicitly to prevent login-CSRF.
@method_decorator(csrf_protect, name="dispatch")
class RegisterView(AuthThrottleMixin, generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        login(self.request, user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(UserSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class PasswordResetRequestView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"], is_active=True
        ).first()
        if user is not None:
            send_password_reset_email.delay(user.pk)
        # Same response whether the email exists or not: no user enumeration.
        return Response(
            {"detail": "If an account with this email exists, a reset link has been sent."}
        )


class PasswordResetConfirmView(AuthThrottleMixin, APIView):
    """
    GET  ?uid=...&token=...  -> checks the link from the email (no side effects).
    POST {uid, token, new_password} -> sets the new password.
    """

    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def get(self, request):
        serializer = PasswordResetLinkSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "detail": "Link is valid. POST uid, token and new_password to this URL.",
                "uid": serializer.validated_data["uid"],
                "token": serializer.validated_data["token"],
            }
        )

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password has been reset."})
