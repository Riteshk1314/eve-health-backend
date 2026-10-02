from django.urls import path

from . import views

urlpatterns = [
    path("payments/", views.payment_list, name="payment-list"),
    path("payments/webhook/", views.payment_webhook, name="payment-webhook"),
    path("payments/<int:payment_id>/", views.payment_detail, name="payment-detail"),
]
