from rest_framework import serializers

from .models import Payment
from .webhooks import EVENT_TO_PAYMENT_STATUS


class PaymentSerializer(serializers.ModelSerializer):
    booking_status = serializers.CharField(source="booking.status", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "booking", "booking_status", "amount", "status",
            "provider_reference", "failure_reason", "created_at", "updated_at",
        ]
        read_only_fields = fields


class PaymentCreateSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField(min_value=1)


class WebhookDataSerializer(serializers.Serializer):
    provider_reference = serializers.CharField(max_length=64)
    failure_reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class WebhookEventSerializer(serializers.Serializer):
    event_id = serializers.CharField(max_length=100)
    type = serializers.ChoiceField(choices=list(EVENT_TO_PAYMENT_STATUS))
    data = WebhookDataSerializer()
