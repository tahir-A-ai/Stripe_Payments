from django.contrib import admin
from django.urls import path
from django.urls import include
from rest_framework_simplejwt.views import (TokenRefreshView)
from payments.views import CustomTokenView, LoginView, OTPVerificationView
from payments.views import (
    GoogleLoginView,GoogleAuthURLView,
    GitHubAuthURLView, GitHubLoginView,
    LinkedInAuthURLView, LinkedInLoginView,
    TOTPSetupView, TOTPVerifySetupView, VerifyTOTPLoginView
    )

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', CustomTokenView.as_view()),
    path('api/token/refresh/', TokenRefreshView.as_view()),
    path('api/auth/login/', LoginView.as_view(), name='login'),
    path('api/auth/verify-2fa/', OTPVerificationView.as_view(), name='verify_2fa'),

    path('api/auth/totp/setup/', TOTPSetupView.as_view(), name='totp_setup'),
    path('api/auth/totp/verify-setup/', TOTPVerifySetupView.as_view(), name='totp_verify_setup'),
    path('api/auth/totp/verify-login/', VerifyTOTPLoginView.as_view(), name='totp_verify_login'),


    path('api/auth/google/', GoogleLoginView.as_view(), name='google_login'),
    path('api/auth/google/url/', GoogleAuthURLView.as_view(), name='google_auth_url'),

    # --- GITHUB ---
    path('api/auth/github/url/', GitHubAuthURLView.as_view()),
    path('api/auth/github/', GitHubLoginView.as_view()),

    # --- LINKEDIN ---
    path('api/auth/linkedin/url/', LinkedInAuthURLView.as_view()),
    path('api/auth/linkedin/', LinkedInLoginView.as_view()),

    path('api/payments/', include('payments.urls'))
]