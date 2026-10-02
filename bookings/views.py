from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Booking
from .serializers import BookingSerializer


def get_bookings_for_user(user):
    all_bookings = Booking.objects.select_related("centre", "test")
    if user.is_staff:
        return all_bookings
    return all_bookings.filter(user=user)


def find_booking(user, booking_id):
    try:
        return get_bookings_for_user(user).get(id=booking_id)
    except Booking.DoesNotExist:
        return None


def not_found_response():
    return Response({"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(methods=["GET"], responses=BookingSerializer(many=True))
@extend_schema(methods=["POST"], request=BookingSerializer, responses={201: BookingSerializer})
@api_view(["GET", "POST"])
def booking_list(request):
    if request.method == "POST":
        return create_booking(request)
    return list_bookings(request)


def list_bookings(request):
    bookings = get_bookings_for_user(request.user)
    wanted_status = request.query_params.get("status")
    if wanted_status:
        bookings = bookings.filter(status=wanted_status.upper())

    paginator = PageNumberPagination()
    bookings_on_this_page = paginator.paginate_queryset(bookings, request)
    serializer = BookingSerializer(bookings_on_this_page, many=True, context={"request": request})
    return paginator.get_paginated_response(serializer.data)


def create_booking(request):
    serializer = BookingSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        serializer.save(user=request.user)
    except IntegrityError:
        # Two identical requests at the same moment: the unique constraint let only one in.
        return Response(
            {"detail": "You already have an active booking for this slot."},
            status=status.HTTP_409_CONFLICT,
        )

    return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(responses=BookingSerializer)
@api_view(["GET"])
def booking_detail(request, booking_id):
    booking = find_booking(request.user, booking_id)
    if booking is None:
        return not_found_response()

    serializer = BookingSerializer(booking, context={"request": request})
    return Response(serializer.data)


@extend_schema(request=None, responses=BookingSerializer)
@api_view(["POST"])
def booking_cancel(request, booking_id):
    booking = find_booking(request.user, booking_id)
    if booking is None:
        return not_found_response()

    with transaction.atomic():
        # Lock the row so a payment webhook can't confirm it while we cancel.
        booking = Booking.objects.select_for_update().get(id=booking.id)

        if not booking.can_transition_to(Booking.Status.CANCELLED):
            return Response(
                {"detail": f"Cannot cancel a booking that is {booking.status}."},
                status=status.HTTP_409_CONFLICT,
            )

        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])

    serializer = BookingSerializer(booking, context={"request": request})
    return Response(serializer.data)
