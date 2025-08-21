from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


# ------------------- Custom JWT serializer -------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends SimpleJWT's TokenObtainPairSerializer to add extra user info
    in the token response (and add custom claims to the token itself).
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['first_name'] = getattr(user, 'first_name', '')
        token['last_name'] = getattr(user, 'last_name', '')
        token['role'] = getattr(user, 'role', None)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserProfileSerializer(self.user).data
        return data


# ------------------- Registration -------------------
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    profile_picture = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
        'email', 'first_name', 'last_name', 'phone_number', 'role', 'password', 'confirm_password', 'profile_picture')

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        try:
            validate_password(attrs['password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})

        return attrs

    def create(self, validated_data):
        profile_picture = validated_data.pop('profile_picture', None)
        validated_data.pop('confirm_password', None)
        user = User.objects.create_user(**validated_data)
        if profile_picture:
            user.profile_picture = profile_picture
            user.save()

        return user


# ------------------- Profile -------------------
class UserProfileSerializer(serializers.ModelSerializer):
    profile_completion = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'phone_number', 'role',
            'profile_picture', 'bio', 'location', 'website', 'linkedin_url',
            'github_url', 'twitter_url', 'resume', 'current_position',
            'education', 'experience_years', 'company_name', 'company_size',
            'company_website', 'company_description', 'is_verified',
            'created_at', 'updated_at', 'profile_completion'
        )
        read_only_fields = ('id', 'email', 'is_verified', 'created_at', 'updated_at')

    def get_profile_completion(self, obj):
        return obj.get_profile_completion_percentage()


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'first_name', 'last_name', 'phone_number', 'profile_picture',
            'bio', 'location', 'website', 'linkedin_url', 'github_url',
            'twitter_url', 'resume', 'current_position', 'education',
            'experience_years', 'company_name', 'company_size',
            'company_website', 'company_description'
        )

    def validate(self, attrs):
        user = self.context['request'].user
        if user.role == 'job_seeker':
            if 'company_name' in attrs or 'company_size' in attrs or 'company_website' in attrs or 'company_description' in attrs:
                raise serializers.ValidationError("Company fields are not applicable for job seekers.")
        elif user.role == 'employer':
            if 'resume' in attrs or 'current_position' in attrs or 'education' in attrs or 'experience_years' in attrs:
                raise serializers.ValidationError("Job seeker fields are not applicable for employers.")

        return attrs


# ------------------- Login (optional / alternate to SimpleJWT view) -------------------
class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={'input_type': 'password'}, trim_whitespace=False)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not (email and password):
            raise serializers.ValidationError(_('Must include "email" and "password".'), code='authorization')

        user = authenticate(request=self.context.get('request'), username=email, password=password)
        if not user:
            raise serializers.ValidationError(_('Invalid credentials.'), code='authorization')

        if hasattr(user, 'is_verified') and not user.is_verified:
            raise serializers.ValidationError(_('Account not verified. Please verify your email.'),
                                              code='authorization')

        refresh = RefreshToken.for_user(user)

        attrs['user'] = UserProfileSerializer(user).data
        attrs['tokens'] = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

        return attrs


# ------------------- Password reset request (matches views) -------------------
class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user found with this email address.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(style={'input_type': 'password'}, write_only=True)
    confirm_password = serializers.CharField(style={'input_type': 'password'}, write_only=True)
    token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        try:
            validate_password(attrs['password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})

        return attrs


# ------------------- Email verification / OTP -------------------
class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=10)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value


# ------------------- User Profile Detail Serializer -------------------
class UserProfileDetailSerializer(serializers.ModelSerializer):
    profile_completion = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'phone_number', 'role',
            'is_verified', 'profile_picture', 'bio', 'location', 'website',
            'linkedin_url', 'github_url', 'twitter_url', 'resume', 'current_position',
            'education', 'experience_years', 'company_name',
            'company_size', 'company_website', 'company_description',
            'created_at', 'updated_at', 'profile_completion'
        )
        read_only_fields = ('id', 'email', 'is_verified', 'created_at', 'updated_at')

    def get_profile_completion(self, obj):
        return obj.get_profile_completion_percentage()

