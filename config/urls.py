from django.contrib import admin
from django.urls import path
from django.urls import include
from rest_framework_simplejwt.views import (TokenRefreshView)
from payments.views import CustomTokenView
from payments.views import GoogleLoginView

urlpatterns = [
    path('admin/', admin.site.urls),
     path('api/token/', CustomTokenView.as_view()),
    path('api/token/refresh/', TokenRefreshView.as_view()),
    path('api/auth/google/', GoogleLoginView.as_view(), name='google_login'),
    path('api/payments/', include('payments.urls'))
]