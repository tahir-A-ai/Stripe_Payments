import requests
import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CheckoutSessionSerializer, CustomTokenSerializer
from django.shortcuts import get_object_or_404
from .models import Product, VendorProfile
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.views import TokenObtainPairView

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.linkedin_oauth2.views import LinkedInOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView

stripe.api_key = settings.STRIPE_SECRET_KEY

import os
import urllib.parse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

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