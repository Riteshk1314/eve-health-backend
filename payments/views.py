import logging

from django.db import IntegrityError, transaction
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from bookings.exceptions import Conflict
from bookings.models import Booking
from config.throttles import PaymentThrottle

from . import services, webhooks
from .models import Payment, WebhookEvent
from .serializers import PaymentCreateSerializer, PaymentSerializer, WebhookEventSerializer
from .tasks import process_webhook_event

logger = logging.getLogger(__name__)

MAX_IDEMPOTENCY_KEY_LENGTH = 100


def get_payments_for_user(user):
    payments = Payment.objects.select_related("booking")
    if user.is_staff:
        return payments
    return payments.filter(booking__user=user)


def find_payment(user, payment_id):
    try:
        return get_payments_for_user(user).get(id=payment_id)
    except Payment.DoesNotExist:
        return None


@extend_schema(methods=["GET"], responses=PaymentSerializer(many=True))
@extend_schema(
    methods=["POST"],
    request=PaymentCreateSerializer,
    responses={201: PaymentSerializer, 200: PaymentSerializer},
    parameters=[OpenApiParameter(
        "Idempotency-Key", str, OpenApiParameter.HEADER, required=False,
        description="Retrying with the same key returns the original payment.",
    )],
)
@api_view(["GET", "POST"])
@throttle_classes([UserRateThrottle, PaymentThrottle])
def payment_list(request):
    if request.method == "POST":
        return create_payment(request)
    return list_payments(request)


def list_payments(request):
    payments = get_payments_for_user(request.user)

    paginator = PageNumberPagination()
    payments_on_this_page = paginator.paginate_queryset(payments, request)
    serializer = PaymentSerializer(payments_on_this_page, many=True)
    return paginator.get_paginated_response(serializer.data)


def create_payment(request):
    serializer = PaymentCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    booking_id = serializer.validated_data["booking_id"]

    # A retry with the same Idempotency-Key gets the original payment back
    # instead of creating a second one.
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        if len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
            return Response(
                {"detail": "Idempotency-Key is too long."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        earlier_payment = get_payments_for_user(request.user).filter(
            idempotency_key=idempotency_key
        ).first()
        if earlier_payment is not None:
            return Response(PaymentSerializer(earlier_payment).data, status=status.HTTP_200_OK)

    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
    except Booking.DoesNotExist:
        return Response({"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        payment = services.create_order(booking, idempotency_key=idempotency_key)
    except Conflict as error:
        return Response({"detail": str(error.detail)}, status=status.HTTP_409_CONFLICT)
    except IntegrityError:
        # Two requests at the same moment: the unique constraints let only one through.
        return Response(
            {"detail": "A payment for this booking is already in progress."},
            status=status.HTTP_409_CONFLICT,
        )

    # Always PENDING here: the provider sends the result later to the webhook.
    return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


@extend_schema(responses=PaymentSerializer)
@api_view(["GET"])
def payment_detail(request, payment_id):
    payment = find_payment(request.user, payment_id)
    if payment is None:
        return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)

    return Response(PaymentSerializer(payment).data)


# Called by the payment provider, not by users: no JWT (the body is signed
# instead) and no rate limit (dropping the provider's retries would lose results).
@extend_schema(request=WebhookEventSerializer, responses={202: None, 200: None})
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def payment_webhook(request):
    # The signature must be checked on the raw bytes, exactly as they arrived.
    signature = request.headers.get(webhooks.SIGNATURE_HEADER, "")
    if not webhooks.is_valid_signature(request.body, signature):
        logger.warning("webhook_bad_signature")
        return Response({"detail": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = WebhookEventSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    event_id = serializer.validated_data["event_id"]
    event_type = serializer.validated_data["type"]
    provider_reference = serializer.validated_data["data"]["provider_reference"]

    payment = Payment.objects.filter(provider_reference=provider_reference).first()
    if payment is None:
        return Response({"detail": "Unknown payment reference."}, status=status.HTTP_404_NOT_FOUND)

    # event_id is unique, so even two simultaneous deliveries store one row.
    event, created = WebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={"event_type": event_type, "payment": payment, "payload": request.data},
    )

    if not created:
        if event.status != WebhookEvent.Status.FAILED:
            logger.info("webhook_duplicate", extra={"event_id": event_id, "status": event.status})
            return Response({"detail": "Duplicate event ignored.", "event_status": event.status})

        # We gave up on this event earlier and the provider re-sent it: try again.
        event.status = WebhookEvent.Status.RECEIVED
        event.save(update_fields=["status"])

    # on_commit: the worker must not start before the event row is saved.
    transaction.on_commit(lambda: process_webhook_event.delay(event.pk))

    logger.info("webhook_accepted", extra={"event_id": event_id, "type": event_type})
    return Response({"detail": "Event accepted."}, status=status.HTTP_202_ACCEPTED)
