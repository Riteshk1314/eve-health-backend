import logging

from django.db import transaction

from bookings.exceptions import Conflict
from bookings.models import Booking

from . import gateway
from .models import Payment

logger = logging.getLogger(__name__)

PAYABLE_BOOKING_STATUSES = [Booking.Status.PENDING, Booking.Status.FAILED]


def create_order(booking, idempotency_key=None):
    with transaction.atomic():
        # Lock the booking so two requests can't both pass the checks below.
        booking = Booking.objects.select_for_update().get(pk=booking.pk)

        if booking.status not in PAYABLE_BOOKING_STATUSES:
            raise Conflict(f"Booking is {booking.status} and cannot be paid.")
        if booking.payments.filter(status=Payment.Status.PENDING).exists():
            raise Conflict("A payment for this booking is already in progress.")

        payment = Payment.objects.create(
            booking=booking, amount=booking.amount, idempotency_key=idempotency_key
        )

    # Outside the transaction so a slow provider doesn't keep the booking locked.
    gateway.create_order(payment.provider_reference, payment.amount)

    logger.info("order_created", extra={"payment_id": payment.id, "booking_id": booking.id})
    return payment


def process_payment(payment_id, new_status, failure_reason=""):
    # The only place a payment is finalised. Already-final payments are left
    # untouched, which makes repeated or late webhooks harmless.
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id)
        booking = Booking.objects.select_for_update().get(pk=payment.booking_id)

        if payment.is_final:
            if payment.status != new_status:
                logger.warning(
                    "payment_result_ignored",
                    extra={"payment_id": payment.id, "current": payment.status, "received": new_status},
                )
            return payment

        payment.status = new_status
        if new_status == Payment.Status.FAILED:
            payment.failure_reason = failure_reason
        else:
            payment.failure_reason = ""
        payment.save(update_fields=["status", "failure_reason", "updated_at"])

        if new_status == Payment.Status.SUCCESS:
            booking_status = Booking.Status.CONFIRMED
        else:
            booking_status = Booking.Status.FAILED

        if booking.can_transition_to(booking_status):
            booking.transition_to(booking_status)
            booking.save(update_fields=["status", "updated_at"])
        elif new_status == Payment.Status.SUCCESS:
            # Money taken but the booking was cancelled meanwhile: needs a manual refund.
            logger.warning(
                "refund_required",
                extra={"payment_id": payment.id, "booking_id": booking.id, "booking_status": booking.status},
            )

    logger.info(
        "payment_processed",
        extra={"payment_id": payment.id, "status": payment.status, "booking_status": booking.status},
    )
    return payment
