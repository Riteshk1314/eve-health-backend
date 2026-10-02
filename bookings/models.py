from django.conf import settings
from django.db import models

from centres.models import DiagnosticCentre, DiagnosticTest


class InvalidTransition(Exception):
    pass


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        CONFIRMED = "CONFIRMED"
        FAILED = "FAILED"
        CANCELLED = "CANCELLED"

    ALLOWED_TRANSITIONS = {
        Status.PENDING: {Status.CONFIRMED, Status.FAILED, Status.CANCELLED},
        Status.FAILED: {Status.CONFIRMED, Status.CANCELLED},
        Status.CONFIRMED: {Status.CANCELLED},
        Status.CANCELLED: set(),
    }
    ACTIVE_STATUSES = [Status.PENDING, Status.CONFIRMED]

    # PROTECT: anything with bookings can't be hard-deleted (centres/tests are soft-deleted).
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    centre = models.ForeignKey(DiagnosticCentre, on_delete=models.PROTECT, related_name="bookings")
    test = models.ForeignKey(DiagnosticTest, on_delete=models.PROTECT, related_name="bookings")
    appointment_at = models.DateTimeField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="booking_amount_positive"),
            models.UniqueConstraint(
                fields=["user", "centre", "test", "appointment_at"],
                condition=models.Q(status__in=["PENDING", "CONFIRMED"]),
                name="unique_active_booking",
            ),
        ]

    def __str__(self):
        return f"Booking #{self.pk} {self.user} - {self.test} [{self.status}]"

    def can_transition_to(self, new_status):
        return new_status in self.ALLOWED_TRANSITIONS[self.status]

    def transition_to(self, new_status):
        if not self.can_transition_to(new_status):
            raise InvalidTransition(f"Cannot move booking from {self.status} to {new_status}.")
        self.status = new_status
