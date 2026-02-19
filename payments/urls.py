from django.urls import path
from .views import( 
    CreateCheckoutSessionView, ConnectStripeView, 
    StripeCallbackView, CreateVendorPayoutView,
    CreatePlatformPayoutView,
    )
from django.views.generic import TemplateView

urlpatterns = [
    path('create-checkout-session/', CreateCheckoutSessionView.as_view(), name='create-checkout-session'),
    path('success/', TemplateView.as_view(template_name='payments/success.html'), name='payment-success'),
    path('cancel/', TemplateView.as_view(template_name='payments/cancel.html'), name='payment-cancel'),
    path('connect-stripe/', ConnectStripeView.as_view(), name='connect-stripe'),
    path('oauth/callback/', StripeCallbackView.as_view(), name='stripe-callback'),
    path('create-vendor-payout/', CreateVendorPayoutView.as_view(), name='create-vendor-payout'),
    path('create-platform-payout/', CreatePlatformPayoutView.as_view(), name='create-platform-payout')
]