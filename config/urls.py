from django.contrib import admin
from django.urls import path
from django.urls import include
from rest_framework_simplejwt.views import (TokenRefreshView)
from payments.views import CustomTokenView
from payments.views import (
    GoogleLoginView,GoogleAuthURLView,
    GitHubAuthURLView, GitHubLoginView,
    LinkedInAuthURLView, LinkedInLoginView
    )

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', CustomTokenView.as_view()),
    path('api/token/refresh/', TokenRefreshView.as_view()),
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