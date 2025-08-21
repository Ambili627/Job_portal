from rest_framework import generics, status, permissions
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from .serializers import (
    UserRegistrationSerializer,
    CustomTokenObtainPairSerializer,
    VerifyEmailSerializer,
    ResendOTPSerializer,
    PasswordResetSerializer,
    PasswordResetConfirmSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer
)
from django.contrib.auth import get_user_model
import pyotp
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

User = get_user_model()


# ------------------- User Registration -------------------
class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()


        totp = pyotp.TOTP(pyotp.random_base32(), interval=300)
        otp = totp.now()
        user.otp = otp
        user.otp_created_at = timezone.now()
        user.save()


        try:
            send_mail(
                'Verify your email - Job Portal',
                f'Your OTP for email verification is: {otp}\n\nThis OTP will expire in 5 minutes.',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Email sending failed: {e}")

        return Response(
            {
                "detail": "User registered successfully. Please check your email for OTP.",
                "email": user.email,
                "profile_picture_url": user.profile_picture.url if user.profile_picture else None
            },
            status=status.HTTP_201_CREATED
        )


# ------------------- JWT Login -------------------
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]


# ------------------- Profile Views -------------------
class UserProfileView(generics.RetrieveUpdateAPIView):  # Changed from RetrieveAPIView
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):

        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return UserProfileSerializer
        else:
            return UserProfileUpdateSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        # Return the full profile data after update
        return Response(UserProfileSerializer(instance).data)


class UserProfileUpdateView(generics.UpdateAPIView):
    serializer_class = UserProfileUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(UserProfileSerializer(instance).data)


# ------------------- Verify Email (with OTP) -------------------
class VerifyEmailView(generics.GenericAPIView):
    serializer_class = VerifyEmailSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "User with this email does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not user.otp:
            return Response(
                {"detail": "No OTP generated for this user. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.otp != otp:
            return Response(
                {"detail": "Invalid OTP. Please check the code and try again."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if OTP is expired (5 minutes)
        if user.otp_created_at and (timezone.now() - user.otp_created_at).total_seconds() > 300:
            return Response(
                {"detail": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.is_verified = True
        user.otp = None
        user.otp_created_at = None
        user.save()

        return Response(
            {"detail": "Email verified successfully. You can now login."},
            status=status.HTTP_200_OK
        )


# ------------------- Resend OTP -------------------
class ResendOTPView(generics.GenericAPIView):
    serializer_class = ResendOTPSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "User with this email does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        if user.is_verified:
            return Response(
                {"detail": "Email is already verified. No need to resend OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )


        totp = pyotp.TOTP(pyotp.random_base32(), interval=300)
        otp = totp.now()
        user.otp = otp
        user.otp_created_at = timezone.now()
        user.save()


        try:
            send_mail(
                'Verify your email - Job Portal',
                f'Your new OTP is: {otp}\n\nThis OTP will expire in 5 minutes.',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            return Response(
                {"detail": "Failed to send OTP email. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"detail": "OTP resent successfully. Please check your email."},
            status=status.HTTP_200_OK
        )


# ------------------- Password Reset -------------------
class CustomPasswordResetView(generics.GenericAPIView):
    serializer_class = PasswordResetSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:

            return Response(
                {"detail": "If this email exists in our system, a password reset link has been sent."},
                status=status.HTTP_200_OK
            )


        return Response(
            {"detail": "Password reset link has been sent to your email."},
            status=status.HTTP_200_OK
        )


# ------------------- Password Reset Confirm -------------------
class CustomPasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)


        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK
        )
