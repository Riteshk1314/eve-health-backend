import uuid

from django.db import models

from bookings.models import Booking


def new_provider_reference():
    return f"pay_{uuid.uuid4().hex}"


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"

    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    provider_reference = models.CharField(max_length=64, unique=True, default=new_provider_reference)
    idempotency_key = models.CharField(max_length=100, null=True, blank=True, unique=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payment_amount_positive"),
            # Database-level guarantee against double charging.
            models.UniqueConstraint(
                fields=["booking"], condition=models.Q(status="SUCCESS"),
                name="one_successful_payment_per_booking",
            ),
            models.UniqueConstraint(
                fields=["booking"], condition=models.Q(status="PENDING"),
                name="one_pending_payment_per_booking",
            ),
        ]

    def __str__(self):
        return f"{self.provider_reference} [{self.status}]"

    @property
    def is_final(self):
        return self.status != self.Status.PENDING


class WebhookEvent(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "RECEIVED"
        PROCESSED = "PROCESSED"
        FAILED = "FAILED"

    # Unique event_id is what makes a re-delivered webhook a no-op.
    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=50)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="webhook_events")
    payload = models.JSONField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RECEIVED)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.event_id} ({self.event_type}) [{self.status}]"
