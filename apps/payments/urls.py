from django.urls import path, re_path, include

from apps.payments import views

app_name = 'payments'

urlpatterns = [
    path('create-checkout-session/', views.CreateCheckoutSessionApiView.as_view(), name='create-checkout-session'),
    path('subscription/', views.SubscriptionApiView.as_view(), name='subscription'),
    path('create-billing-portal-session/', views.CreateBillingPortalSessionApiView.as_view(), name='create-billing-portal-session'),
    path('webhook/', views.StripeWebhookApiView.as_view(), name='webhook'),
    re_path(r'^v1/', include([
        re_path(r'^payments/', include([
            path('create-checkout-session/', views.CreateCheckoutSessionApiView.as_view(), name='v1-create-checkout-session'),
            path('subscription/', views.SubscriptionApiView.as_view(), name='v1-subscription'),
            path('create-billing-portal-session/', views.CreateBillingPortalSessionApiView.as_view(), name='v1-create-billing-portal-session'),
            path('webhook/', views.StripeWebhookApiView.as_view(), name='v1-webhook'),
        ])),
    ])),
]
