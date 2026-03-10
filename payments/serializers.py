from typing import Required

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import OTPVerification

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        return attrs

class OTPVerificationSerializer(serializers.Serializer):
    session_token = serializers.CharField(required=True)
    otp_code = serializers.CharField(required=True)

    # def validate(self, value):
    #     if not value.isdigit():
    #         return({'error': 'OTP code must be 6 digits'})
    #     return value


class TOTPSetupSerializer(serializers.Serializer):
    secret_key = serializers.CharField()
    message = serializers.CharField()
    instructions = serializers.CharField()

class TOTPVerifySetupSerializer(serializers.Serializer):
    totp_code = serializers.CharField(required=True)

class TOTPVerificationSerializer(serializers.Serializer):
    totp_code = serializers.CharField(required=True)

class TOTPVerificationLoginSerializer(serializers.Serializer):
    session_token = serializers.CharField()
    totp_code = serializers.CharField(max_length=6, min_length=6)


class LoginResponseSerializer(serializers.Serializer):
    """Response when 2FA is required"""
    requires_2fa = serializers.BooleanField()
    session_token = serializers.CharField(required=False)
    message = serializers.CharField()
    two_fa_method = serializers.CharField(required=False)
    masked_contact = serializers.CharField(required=False)  # e.g., "+92300****567" or "us***@example.com"

class CheckoutSessionSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)

class CustomTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token['username'] = user.username
        return token