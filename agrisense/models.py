# models.py
from django.db import models
from django.contrib.auth.models import User


class PlantScan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='scans/')
    disease_detected = models.BooleanField(default=False)
    disease_name = models.CharField(max_length=200, blank=True)
    scientific_name = models.CharField(max_length=200, blank=True)
    confidence = models.FloatField(default=0)
    notification_read = models.BooleanField(default=False)
    severity = models.CharField(max_length=50, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('unknown', 'Unknown')
    ], default='unknown')
    treatment_recommended = models.TextField(blank=True)
    crop_type = models.CharField(max_length=100, blank=True)
    
    # Urdu Translations (Pre-translated and stored)
    disease_name_ur = models.CharField(max_length=200, blank=True)
    treatment_recommended_ur = models.TextField(blank=True)
    crop_type_ur = models.CharField(max_length=100, blank=True)
    severity_ur = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.disease_name} - {self.created_at}"
    
from django.db import models
from django.core.cache import cache

class SiteBranding(models.Model):
    """
    Singleton-like global branding settings.
    Normally there should be only ONE row (id=1).
    """
    app_name = models.CharField(
        max_length=60,
        default="AgriSense",
        help_text="Name shown in sidebar, header, mobile menu etc."
    )
    app_subtitle = models.CharField(
        max_length=80,
        default="Edge Intelligence",
        blank=True,
        help_text="Small text shown below the app name / logo"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Branding"
        verbose_name_plural = "Site Branding"

    def __str__(self):
        return self.app_name

    @classmethod
    def get_current(cls):
        """Get or create the singleton instance"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    # Optional: cache helper (recommended)
    @classmethod
    def cached(cls):
        key = "branding:current"
        branding = cache.get(key)
        if branding is None:
            branding = cls.get_current()
            cache.set(key, branding, timeout=3600 * 24)  # 24h
        return branding

# models.py (add this to your existing models.py)

# Add this model to store team member applications
# Add this to your existing models.py

class TeamApplication(models.Model):
    """
    Model to store team join applications
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Full Name")
    name_ur = models.CharField(max_length=100, blank=True, verbose_name="Full Name (Urdu)")
    email = models.EmailField(verbose_name="Email Address")
    role = models.CharField(max_length=100, verbose_name="Desired Role")
    role_ur = models.CharField(max_length=100, blank=True, verbose_name="Desired Role (Urdu)")
    message = models.TextField(blank=True, verbose_name="Introduction/Message")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Applied By")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Application Status")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Submitted At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Last Updated")
    
    class Meta:
        verbose_name = "Team Application"
        verbose_name_plural = "Team Applications"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.role} ({self.get_status_display()})"

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    """
    Extended user profile for storing preferences and additional settings.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    high_risk_notifications = models.BooleanField(
        default=True,
        help_text="Receive notifications when high-risk diseases are detected"
    )
    theme_preference = models.CharField(
        max_length=10,
        choices=[('light', 'Light'), ('dark', 'Dark')],
        default='light',
        help_text="User's preferred theme"
    )
    email_notifications = models.BooleanField(
        default=True,
        help_text="Receive email notifications for important updates"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
    
    def __str__(self):
        return f"{self.user.username}'s Profile"


# Auto-create UserProfile when a new User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

# Add this to your existing models.py

# Add to your existing models.py

class TutorialVideo(models.Model):
    """
    Model to store uploaded tutorial video (supports up to 1GB)
    """
    title = models.CharField(max_length=200, default="AgriSense Tutorial", help_text="Video title")
    video_file = models.FileField(
        upload_to='tutorial_videos/', 
        help_text="Upload MP4 video file (max 1GB)",
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True, help_text="Show this video on the website")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tutorial Video"
        verbose_name_plural = "Tutorial Videos"
    
    def __str__(self):
        return self.title
    
    def file_size_mb(self):
        """Return file size in MB"""
        if self.video_file:
            return round(self.video_file.size / (1024 * 1024), 2)
        return 0
    
    @classmethod
    def get_active_video(cls):
        """Get the active tutorial video"""
        try:
            return cls.objects.filter(is_active=True).first()
        except:
            return None

class StaticContent(models.Model):
    """
    Stores localized content for static UI elements across different pages.
    Allows for high-performance, database-backed translations.
    """
    PAGE_CHOICES = [
        ('dashboard', 'Dashboard'),
        ('scanner', 'Scanner'),
        ('history', 'History'),
        ('about', 'About'),
        ('profile', 'Profile'),
        ('settings', 'Settings'),
        ('global', 'Global/Shared'),
    ]
    
    page = models.CharField(max_length=50, choices=PAGE_CHOICES, default='global')
    key = models.CharField(max_length=100)
    text_en = models.TextField(help_text="Original English text")
    text_ur = models.TextField(blank=True, help_text="Urdu translation")
    
    class Meta:
        unique_together = ('page', 'key')
        verbose_name = "Static UI Content"
        verbose_name_plural = "Static UI Content"

    def __str__(self):
        return f"{self.page} - {self.key}"

class CropCategory(models.Model):
    """
    Information about different crop types to be shown in the UI.
    """
    name = models.CharField(max_length=100, unique=True, help_text="Crop name (e.g., Orange, Apple, Corn)")
    name_ur = models.CharField(max_length=100, blank=True, help_text="Crop name in Urdu")
    description = models.TextField(help_text="Detailed information about this crop category")
    description_ur = models.TextField(blank=True, help_text="Detailed information in Urdu")
    icon = models.CharField(max_length=50, default="psychology", help_text="Material Symbol icon name")
    
    class Meta:
        verbose_name = "Crop Category"
        verbose_name_plural = "Crop Categories"
        
    def __str__(self):
        return self.name