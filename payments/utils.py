import random
import string
from django.core.mail import send_mail
from django.conf import settings
from twilio.rest import Client

def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


def generate_session_token():
    """Generate a unique session token for temporary authentication"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=64))


def send_otp_via_sms(phone_number, otp_code):
    """Send OTP via Twilio SMS"""
    try:
        # Initialize Twilio client
        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        
        message = client.messages.create(
            body=f"Your verification code is: {otp_code}\n\nThis code will expire in 5 minutes.",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        
        return True, message.sid
    except Exception as e:
        return False, str(e)


def send_otp_via_email(email, otp_code):
    """Send OTP via Email"""
    try:
        subject = "Your Verification Code"
        message = f"""
Hello,

Your verification code is: {otp_code}

This code will expire in 5 minutes.

If you didn't request this code, please ignore this email.

Best regards,
Your App Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        return True, "Email sent successfully"
    except Exception as e:
        return False, str(e)