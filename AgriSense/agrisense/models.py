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
    crop_type = models.CharField(max_length=100, blank=True)  # Add this field
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