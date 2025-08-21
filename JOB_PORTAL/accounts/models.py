from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
import os


class UserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


def user_profile_picture_path(instance, filename):
    """File path for user profile pictures"""
    return f'profile_pictures/user_{instance.id}/{filename}'


def user_resume_path(instance, filename):
    """File path for user resumes"""
    return f'resumes/user_{instance.user.id}/{filename}'


class User(AbstractUser):
    """Custom User model with email as username."""

    ROLE_CHOICES = (
        ('job_seeker', 'Job Seeker'),
        ('employer', 'Employer'),
        ('admin', 'Admin'),
        ('recruiter', 'Recruiter'),
    )

    username = None
    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(_('first name'), max_length=30, blank=False)
    last_name = models.CharField(_('last name'), max_length=30, blank=False)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='job_seeker')
    profile_picture = models.ImageField(upload_to=user_profile_picture_path, null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=100, blank=True, null=True)  # Added missing field
    website = models.URLField(blank=True, null=True)  # Added missing field
    linkedin_url = models.URLField(blank=True, null=True)  # Added missing field
    github_url = models.URLField(blank=True, null=True)  # Added missing field
    twitter_url = models.URLField(blank=True, null=True)  # Added missing field
    is_verified = models.BooleanField(default=False)
    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Job seeker specific fields
    resume = models.FileField(upload_to=user_resume_path, null=True, blank=True)  # Added missing field
    current_position = models.CharField(max_length=100, blank=True, null=True)  # Added missing field
    education = models.CharField(max_length=200, blank=True, null=True)  # Added missing field
    experience_years = models.IntegerField(null=True, blank=True)  # Added missing field

    # Employer specific fields
    company_name = models.CharField(max_length=100, blank=True, null=True)  # Added missing field
    company_size = models.CharField(max_length=50, blank=True, null=True)  # Added missing field
    company_website = models.URLField(blank=True, null=True)  # Added missing field
    company_description = models.TextField(blank=True, null=True)  # Added missing field

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    def set_otp(self, otp_code):
        """Set OTP and timestamp"""
        self.otp = otp_code
        self.otp_created_at = timezone.now()
        self.save()

    def is_otp_valid(self):
        """Check if OTP is still valid (5 minutes)"""
        if not self.otp_created_at or not self.otp:
            return False
        return (timezone.now() - self.otp_created_at).total_seconds() <= 300

    def get_profile_completion_percentage(self):
        """Calculate profile completion percentage"""
        fields = [
            self.first_name, self.last_name, self.phone_number,
            self.profile_picture, self.bio, self.location
        ]

        if self.role == 'job_seeker':
            fields.extend([self.resume, self.current_position, self.education, self.experience_years])
        elif self.role == 'employer':
            fields.extend([self.company_name, self.company_description, self.company_website])

        completed = sum(1 for field in fields if field)
        total = len(fields)
        return int((completed / total) * 100) if total > 0 else 0

    def _str_(self):
        return self.email

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')


class UserProfile(models.Model):
    """Extended profile information for users"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_profile')
    resume = models.FileField(upload_to=user_resume_path, null=True, blank=True)
    website = models.URLField(blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    github_url = models.URLField(blank=True, null=True)
    twitter_url = models.URLField(blank=True, null=True)

    # Job seeker specific fields
    current_position = models.CharField(max_length=100, blank=True, null=True)
    current_company = models.CharField(max_length=100, blank=True, null=True)
    seeking_job = models.BooleanField(default=True)
    desired_salary = models.CharField(max_length=50, blank=True, null=True)
    open_to_relocation = models.BooleanField(default=False)

    # Employer specific fields
    company_name = models.CharField(max_length=100, blank=True, null=True)
    company_size = models.CharField(max_length=50, blank=True, null=True)
    company_website = models.URLField(blank=True, null=True)
    hiring_role = models.CharField(max_length=100, blank=True, null=True)

    def _str_(self):
        return f"{self.user.email}'s Profile"

    class Meta:
        verbose_name = _('User Profile')
        verbose_name_plural = _('User Profiles')


class Skill(models.Model):
    """Skills for job seekers"""
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=100)
    proficiency = models.CharField(max_length=20, choices=(
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert'),
    ), default='intermediate')

    def _str_(self):
        return f"{self.name} ({self.proficiency})"

    class Meta:
        verbose_name = _('Skill')
        verbose_name_plural = _('Skills')


class Education(models.Model):
    """Education history for job seekers"""
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='education')
    institution = models.CharField(max_length=200)
    degree = models.CharField(max_length=100)
    field_of_study = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    currently_studying = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    def _str_(self):
        return f"{self.degree} at {self.institution}"

    class Meta:
        verbose_name = _('Education')
        verbose_name_plural = _('Education')


class Experience(models.Model):
    """Work experience for job seekers"""
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='experience')
    company = models.CharField(max_length=200)
    position = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    currently_working = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    def _str_(self):
        return f"{self.position} at {self.company}"

    class Meta:
        verbose_name = _('Experience')
        verbose_name_plural = _('Experiences')


class CompanyProfile(models.Model):
    """Company profile for employers"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company_profile')
    company_name = models.CharField(max_length=200)
    industry = models.CharField(max_length=100)
    company_size = models.CharField(max_length=50, choices=(
        ('1-10', '1-10 employees'),
        ('11-50', '11-50 employees'),
        ('51-200', '51-200 employees'),
        ('201-500', '201-500 employees'),
        ('501-1000', '501-1000 employees'),
        ('1000+', '1000+ employees'),
    ))
    website = models.URLField()
    description = models.TextField()
    founded_year = models.IntegerField(null=True, blank=True)
    headquarters = models.CharField(max_length=100, blank=True, null=True)

    def _str_(self):
        return self.company_name

    class Meta:
        verbose_name = _('Company Profile')
        verbose_name_plural = _('Company Profiles')


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def _str_(self):
        return f"Password reset token for {self.user.email}"

    def is_valid(self):
        """Check if token is still valid (24 hours)"""
        return (timezone.now() - self.created_at).total_seconds() <= 86400 and not self.is_used

    class Meta:
        verbose_name = _('Password Reset Token')
        verbose_name_plural = _('Password Reset Tokens')