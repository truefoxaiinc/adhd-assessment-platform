from django.urls import include, path, re_path

from apps.payments import views

app_name = 'payments'

urlpatterns = [
    re_path(r'^v1/', include([
        re_path(r'^payments/', include([
            path('verify-in-app-purchase/', views.VerifyInAppPurchaseApiView.as_view(), name='verify-in-app-purchase'),
            path('entitlement/', views.EntitlementApiView.as_view(), name='entitlement'),
            path('link-guest-entitlement/', views.LinkGuestEntitlementApiView.as_view(), name='link-guest-entitlement'),
            path('purchase-account-identifiers/', views.PurchaseAccountIdentifiersApiView.as_view(), name='purchase-account-identifiers'),
            path('notifications/google-play/', views.GoogleRtdnApiView.as_view(), name='google-rtdn'),
            path('notifications/app-store/', views.AppleServerNotificationApiView.as_view(), name='apple-notifications'),
        ])),
    ])),
]
