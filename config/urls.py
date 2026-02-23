from django.contrib import admin
from django.urls import path
from django.urls import include
from rest_framework_simplejwt.views import (TokenRefreshView)
from payments.views import CustomTokenView

urlpatterns = [
    path('admin/', admin.site.urls),
     path('api/token/', CustomTokenView.as_view()),
    path('api/token/refresh/', TokenRefreshView.as_view()),
    path('api/payments/', include('payments.urls'))
]