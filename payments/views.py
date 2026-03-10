from rest_framework.response import Response
import stripe
import os
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
import urllib.parse
from rest_framework.views import APIView
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework import status
from .serializers import (
    CheckoutSessionSerializer, CustomTokenSerializer, 
    LoginResponseSerializer, LoginSerializer,
    OTPVerificationSerializer, TOTPSetupSerializer,
    TOTPVerifySetupSerializer,TOTPVerificationSerializer, 
    TOTPVerificationLoginSerializer,
    )
from django.shortcuts import get_object_or_404
from .models import Product, VendorProfile, UserProfile, OTPVerification
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.views import TokenObtainPairView
from .utils import (
    generate_otp, 
    generate_session_token, 
    send_otp_via_sms, 
    send_otp_via_email
)
from .totp_utils import (
    generate_totp_secret,
    verify_totp_code,
    get_current_totp_code
)

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.linkedin_oauth2.views import LinkedInOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView

stripe.api_key = settings.STRIPE_SECRET_KEY

class LoginView(APIView):
    """
    User login with password
    If 2FA is enabled, generate and send OTP
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        user = authenticate(username=username, password=password)

        if user is None:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Check if user has 2FA enabled
        try:
            user_profile = user.profile
        except UserProfile.DoesNotExist:
            # Create profile if doesn't exist (for testing)
            user_profile = UserProfile.objects.create(user=user)

        if not user_profile.two_fa_enabled:
            refresh = CustomTokenSerializer.get_token(user)
            return Response({
                'requires_2fa': False,
                'message': 'Login successful. No 2FA required.',
                'token': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh)
                },
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            })

        # 2FA is enabled - check method
        if user_profile.two_fa_method == 'totp':
            # TOTP - just ask for code (no SMS/Email sent)
            session_token = generate_session_token()
            
            # Store session temporarily
            OTPVerification.objects.create(
                user=user,
                session_token=session_token,
                purpose='login',
                otp_code='000000'  # Dummy - not used for TOTP
            )
            
            return Response({
                'requires_2fa': True,
                'two_fa_method': 'totp',
                'session_token': session_token,
                'message': 'Enter code from your authenticator app'
            })
        
        else:
            # SMS/Email OTP
            otp_code = generate_otp()
            session_token = generate_session_token()

            # Delete any existing unverified OTP for this user
            OTPVerification.objects.filter(
                user=user,
                verified=False,
                purpose='login'
            ).delete()

            # Create new OTP record
            otp_record = OTPVerification.objects.create(
                user=user,
                otp_code=otp_code,
                session_token=session_token,
                purpose='login',
                phone_number=user_profile.phone_number if user_profile.two_fa_method == 'sms' else None,
                email=user.email if user_profile.two_fa_method == 'email' else None
            )

            # Send OTP based on user's preference
            if user_profile.two_fa_method == 'sms':
                success, result = send_otp_via_sms(user_profile.phone_number, otp_code)
                contact = user_profile.phone_number
                masked_contact = self._mask_phone(contact)
            else:  # email
                success, result = send_otp_via_email(user.email, otp_code)
                contact = user.email
                masked_contact = self._mask_email(contact)

            if not success:
                # Failed to send OTP
                otp_record.delete()
                return Response(
                    {'error': f'Failed to send OTP: {result}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Success - OTP sent
            response_data = {
                'requires_2fa': True,
                'session_token': session_token,
                'message': f'Verification code sent to your {user_profile.two_fa_method}',
                'two_fa_method': user_profile.two_fa_method,
                'masked_contact': masked_contact
            }

            return Response(
                LoginResponseSerializer(response_data).data,
                status=status.HTTP_200_OK
            )
    
    def _mask_phone(self, phone):
        """Mask phone number: +923001234567 -> +92300****567"""
        if len(phone) > 7:
            return phone[:-7] + '****' + phone[-3:]
        return phone
    
    def _mask_email(self, email):
        """Mask email: user@example.com -> us**@example.com"""
        if not email or '@' not in email:
            return '***@***.com'
        username, domain = email.split('@')
        if len(username) > 2:
            masked = username[:2] + '**' + (username[-1] if len(username) > 3 else '')
            return f"{masked}@{domain}"
        return email

class OTPVerificationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_token = serializer.validated_data['session_token']
        otp_code = serializer.validated_data['otp_code']
        try:
            otp_record = OTPVerification.objects.get(
                session_token=session_token,
                verified=False,
                purpose='login'
            )
        except OTPVerification.DoesNotExist:
            return Response(
                {'error':'Invalid session token, or session has expired.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        if otp_record.is_expired():
            otp_record.delete()
            return Response(
                {'error': 'OTP has expired, please login.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if otp_record.attempts>=5:
            otp_record.delete()
            return Response(
                {'error': 'Too many attempts, please login.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if otp_record.otp_code != otp_code:
            otp_record.attempts += 1
            otp_record.save()
            attempts_left = 5 - otp_record.attempts
            return Response(
                {
                    'error': 'Invalid OTP code. Please try again.',
                    'attempts_left': attempts_left
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        user = otp_record.user
        otp_record.verified = True
        otp_record.save()
        otp_record.delete()

        refresh = CustomTokenSerializer.get_token(user)
        return Response(
            {
                'success': True,
                'message': 'Login successful.',
                'token': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh)
                    },
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            },
            status=status.HTTP_200_OK
        )

class TOTPSetupView(APIView):
    """
    Step 1: Generate TOTP secret and show to user
    User must be logged in to enable TOTP
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        # Check if TOTP already enabled
        if user.profile.totp_enabled:
            return Response(
                {'error': 'TOTP is already enabled for your account'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate new secret
        secret = generate_totp_secret()
        
        # Save to profile (unconfirmed)
        user.profile.totp_secret = secret
        user.profile.save()
        
        # Return secret to user
        response_data = {
            'secret_key': secret,
            'message': 'TOTP setup initiated',
            'instructions': (
                '1. Open Google Authenticator app\n'
                '2. Tap "+" or "Add account"\n'
                '3. Choose "Enter a setup key"\n'
                f'4. Account name: {user.username}\n'
                f'5. Enter this key: {secret}\n'
                '6. Choose "Time based"\n'
                '7. Enter the 6-digit code shown in the app to verify'
            )
        }
        
        return Response(
            TOTPSetupSerializer(response_data).data,
            status=status.HTTP_200_OK
        )

class TOTPVerifySetupView(APIView):
    """Verify TOTP code to complete setup"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = TOTPVerifySetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        totp_code = serializer.validated_data['totp_code']
        
        # Check if user has secret
        if not user.profile.totp_secret:
            return Response(
                {'error': 'No TOTP setup found. Please initiate setup first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify the code
        if not verify_totp_code(user.profile.totp_secret, totp_code):
            return Response(
                {'error': 'Invalid TOTP code. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Code is valid - enable TOTP
        user.profile.totp_enabled = True
        user.profile.two_fa_enabled = True
        user.profile.two_fa_method = 'totp'
        user.profile.save()
        
        return Response({
            'success': True,
            'message': 'TOTP 2FA enabled successfully!',
            'two_fa_method': 'totp'
        }, status=status.HTTP_200_OK)

class VerifyTOTPLoginView(APIView):
    """
    Verify TOTP code during login
    """
    permission_classes = []
    authentication_classes = []
    
    def post(self, request):
        serializer = TOTPVerificationLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        session_token = serializer.validated_data['session_token']
        totp_code = serializer.validated_data['totp_code']
        
        # Find session
        try:
            otp_record = OTPVerification.objects.get(
                session_token=session_token,
                purpose='login'
            )
        except OTPVerification.DoesNotExist:
            return Response(
                {'error': 'Invalid session'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = otp_record.user
        
        # Verify TOTP code
        if not verify_totp_code(user.profile.totp_secret, totp_code):
            return Response(
                {'error': 'Invalid TOTP code'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Valid! Complete login
        otp_record.delete()
        
        refresh = CustomTokenSerializer.get_token(user)
        
        return Response({
            'success': True,
            'message': 'Login successful',
            'token': {
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            },
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        }, status=status.HTTP_200_OK)

class GoogleAuthURLView(APIView):
    permission_classes = [AllowAny] 

    def get(self, request, *args, **kwargs):

        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        redirect_uri = "http://localhost:8000/" 

        params = {
            'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'scope': 'email profile',
            'access_type': 'offline',
            'prompt': 'consent'
        }

        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        return Response({'url': url})


class GitHubAuthURLView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, *args, **kwargs):
        base_url = "https://github.com/login/oauth/authorize"
        redirect_uri = "http://localhost:8000/"
        params = {
            'client_id': os.environ.get('GITHUB_CLIENT_ID'),
            'redirect_uri': redirect_uri,
            'scope': 'user:email read:user',
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        return Response({'url': url})
    

class LinkedInAuthURLView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        base_url = "https://www.linkedin.com/oauth/v2/authorization"
        redirect_uri = "http://localhost:8000/" 
        params = {
            'response_type': 'code',
            'client_id': os.environ.get('LINKEDIN_CLIENT_ID'),
            'redirect_uri': redirect_uri,
            'scope': 'openid profile email',
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        return Response({'url': url})
    

class GoogleLoginView(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client
    callback_url = "http://localhost:8000/"

class GitHubLoginView(SocialLoginView):
    adapter_class = GitHubOAuth2Adapter
    client_class = OAuth2Client
    callback_url = "http://localhost:8000/"

class LinkedInLoginView(SocialLoginView):
    adapter_class = LinkedInOAuth2Adapter
    client_class = OAuth2Client
    callback_url = "http://localhost:8000/"

class CustomTokenView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer

class CreateCheckoutSessionView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = CheckoutSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prod_id = serializer.validated_data['product_id']
        qty = serializer.validated_data['quantity']

        product_obj = get_object_or_404(Product, pk=prod_id)

        if not product_obj.vendor or not product_obj.vendor.stripe_account_id:
            return Response(
                {'error': 'Product is not linked to a valid vendor Stripe account.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        vendor_account_id = product_obj.vendor.stripe_account_id
        total_amount = product_obj.price * qty
        platform_fee = int(total_amount * 0.10)

        BASE_URL = "http://localhost:8000"

        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'usd',
                            'unit_amount': product_obj.price, 
                            'product_data': {
                                'name': product_obj.name,
                            },
                        },
                        'quantity': qty,
                    },
                ],
                mode='payment',
                success_url= BASE_URL + '/api/payments/success/',
                cancel_url= BASE_URL + '/api/payments/cancel/',

                payment_intent_data={
                    'application_fee_amount': platform_fee, 
                    'transfer_data': {
                        'destination': vendor_account_id, 
                    },
                },
            )

            return Response({
                'id': checkout_session.id,
                'url': checkout_session.url
            })

        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


""" Express Stripe Account - View"""
class ConnectStripeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            vendor = request.user.vendorprofile

            if not vendor:
                return Response({
                    'error': 'User is not a vendor',
                    'stripe_account_id': None,
                    'url': None
                })

            if not vendor.stripe_account_id:
                account = stripe.Account.create(
                    type="express",
                    country="US",
                    capabilities={
                        "card_payments": {"requested": True},
                        "transfers": {"requested": True},
                    },
                )
                vendor.stripe_account_id = account.id
                vendor.save()

            refresh_url = 'http://localhost:3000/vendor/onboarding/refresh/' 
            return_url = 'http://localhost:3000/vendor/dashboard/'

            account_link = stripe.AccountLink.create(
                account=vendor.stripe_account_id,
                refresh_url=refresh_url,
                return_url=return_url,
                type="account_onboarding",
            )
            return Response({
                'message': 'Account link generated successfully',
                'stripe_account_id': vendor.stripe_account_id,
                'url': account_link.url
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)


""" Standard Stripe Account - View"""
# class ConnectStripeView(APIView):
#     permission_classes=  [IsAuthenticated]
#     def get(self, request, *args, **kwargs):
        
#         try:
#             vendor = request.user.vendorprofile
#             if vendor.stripe_account_id:
#                 return Response({
#                     'message': 'You are already connected!',
#                     'stripe_account_id': vendor.stripe_account_id,
#                     'url': None
#                 })
#         except VendorProfile.DoesNotExist:
#             pass

#         redirect_uri = 'http://localhost:8000/api/payments/oauth/callback/'
#         client_id = settings.STRIPE_CLIENT_ID

#         stripe_url = (
#             f"https://connect.stripe.com/oauth/authorize?"
#             f"response_type=code&"
#             f"client_id={client_id}&"
#             f"scope=read_write&"
#             f"redirect_uri={redirect_uri}"
#         )

#         return Response({'url': stripe_url})
    

# class StripeCallbackView(APIView):
#     permission_classes=  [IsAuthenticated]

#     def get(self, request, *args, **kwargs):
#         code = request.query_params.get('code')
#         if not code:
#             return Response({'error': 'No code provided'}, status=status.HTTP_400_BAD_REQUEST)
#         try:
#             response = requests.post(
#                 'https://connect.stripe.com/oauth/token',
#                 data={
#                     'client_secret': settings.STRIPE_SECRET_KEY,
#                     'code': code,
#                     'grant_type': 'authorization_code'
#                 }
#             )
#             data = response.json()
#             if 'error' in data:
#                 return Response({'error': data.get('error_description')}, status=status.HTTP_400_BAD_REQUEST)

#             stripe_account_id = data['stripe_user_id']
#             user = request.user 

#             vendor_profile, created = VendorProfile.objects.get_or_create(user=user)
#             vendor_profile.stripe_account_id = stripe_account_id
#             vendor_profile.save()

#             return Response({
#                 'success': True, 
#                 'stripe_account_id': stripe_account_id,
#                 'message': 'Vendor successfully connected!'
#             })

#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateVendorPayoutView(APIView):
    permission_classes=  [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            vendor = request.user.vendorprofile
            if not vendor.stripe_account_id:
                return Response({'error': 'Vendor not connected to Stripe'}, status=400)
            
            stripe_account_id = vendor.stripe_account_id
        except Exception:
            return Response({'error': 'User is not a vendor'}, status=400)

        amount = request.data.get('amount') 
        if not amount:
             return Response({'error': 'Amount is required'}, status=400)
        try:
            payout = stripe.Payout.create(
                amount=int(amount),
                currency='usd',
                stripe_account=stripe_account_id, 
            )

            return Response({
                'success': True,
                'payout_id': payout.id,
                'amount': payout.amount,
                'status': payout.status
            })

        except stripe.error.StripeError as e:
            return Response({'error': str(e)}, status=400)


class CreatePlatformPayoutView(APIView):
    permission_classes = [IsAdminUser] 

    def post(self, request, *args, **kwargs):
        amount = request.data.get('amount')

        try:
            payout = stripe.Payout.create(
                amount=int(amount),
                currency='usd',
            )

            return Response({
                'success': True,
                'payout_id': payout.id,
                'status': payout.status
            })

        except stripe.error.StripeError as e:
            return Response({'error': str(e)}, status=400)