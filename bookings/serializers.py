from django.utils import timezone
from rest_framework import serializers

from centres.models import CentreTest

from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    centre_name = serializers.CharField(source="centre.name", read_only=True)
    test_name = serializers.CharField(source="test.name", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "centre", "centre_name", "test", "test_name",
            "appointment_at", "amount", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["amount", "status", "created_at", "updated_at"]

        # DRF would auto-add a unique check that ignores the constraint's
        # "only active bookings" condition, so the check is done in validate().
        validators = []

    def validate_appointment_at(self, appointment_at):
        if appointment_at <= timezone.now():
            raise serializers.ValidationError("Appointment time must be in the future.")
        return appointment_at

    def validate(self, data):
        centre = data["centre"]
        test = data["test"]

        offering = CentreTest.objects.filter(
            centre=centre,
            test=test,
            is_available=True,
            centre__is_active=True,
            test__is_active=True,
        ).first()
        if offering is None:
            raise serializers.ValidationError("This centre does not offer the selected test.")

        user = self.context["request"].user
        already_booked = Booking.objects.filter(
            user=user,
            centre=centre,
            test=test,
            appointment_at=data["appointment_at"],
            status__in=Booking.ACTIVE_STATUSES,
        ).exists()
        if already_booked:
            raise serializers.ValidationError("You already have an active booking for this slot.")

        # Snapshot the price so later price changes don't affect this booking.
        data["amount"] = offering.price
        return data
