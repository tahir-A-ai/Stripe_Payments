import os
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class UserProfile(models.Model):
    """Extended user model to track 2FA settings"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    two_fa_enabled = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    two_fa_method = models.CharField(
        max_length=10, 
        choices=[('sms', 'SMS'), ('email', 'Email'), ('totp', 'Authenticator App')],
        default='sms'
    )
    totp_secret = models.CharField(max_length=32, blank=True, null=True)
    totp_enabled = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    

class OTPVerification(models.Model):
    PURPOSE_CHOICES = [
        ('login', 'Login Verification'),
        ('setup', 'Setup 2FA'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_verifications')
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    otp_code = models.CharField(max_length=6)
    session_token = models.CharField(max_length=100, unique=True)  # Temporary session identifier
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='login')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_token']),
            models.Index(fields=['user', 'verified', 'expires_at']),
        ]

    def __str__(self):
        return f"OTP for {self.user.username} - {self.purpose}"

    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def save(self, *args, **kwargs):
        # Set expiry to 5 minutes from now if not set
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)


class VendorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    stripe_account_id = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return self.user.username
    

class Product(models.Model):
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=100, help_text="Name of the product")
    description = models.TextField(blank=True, null=True, help_text="Description of the product")
    price = models.IntegerField(default=0, help_text="Price of the product in cents")
    
    def __str__(self):
        return self.name
    
    def get_display_price(self):
        return "{0:.2f}".format(self.price / 100)