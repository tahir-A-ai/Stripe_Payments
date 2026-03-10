from django.contrib import admin
from .models import Product, OTPVerification, UserProfile
from .models import VendorProfile


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'stripe_account_id')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price')

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'otp_code', 'session_token', 'purpose', 'verified', 'expires_at')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'two_fa_enabled', 'phone_number', 'two_fa_method')
