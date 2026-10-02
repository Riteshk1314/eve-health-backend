from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .cache import get_from_cache, make_cache_key, save_to_cache
from .models import CentreTest, DiagnosticCentre, DiagnosticTest
from .permissions import IsStaffOrReadOnly
from .serializers import (
    CentreTestSerializer,
    DiagnosticCentreDetailSerializer,
    DiagnosticCentreSerializer,
    DiagnosticTestSerializer,
)

# DELETE on these endpoints is a soft delete (is_active / is_available = False),
# because existing bookings still reference the rows.


def not_found_response(message):
    return Response({"detail": message}, status=status.HTTP_404_NOT_FOUND)


def get_centres_for_user(user):
    if user.is_staff:
        return DiagnosticCentre.objects.all()
    return DiagnosticCentre.objects.filter(is_active=True)


def find_centre(user, centre_id):
    try:
        return get_centres_for_user(user).get(id=centre_id)
    except DiagnosticCentre.DoesNotExist:
        return None


@extend_schema(methods=["GET"], responses=DiagnosticCentreSerializer(many=True))
@extend_schema(methods=["POST"], request=DiagnosticCentreSerializer, responses={201: DiagnosticCentreSerializer})
@api_view(["GET", "POST"])
@permission_classes([IsStaffOrReadOnly])
def centre_list(request):
    if request.method == "POST":
        return create_centre(request)
    return list_centres(request)


def list_centres(request):
    cache_key = make_cache_key(request)
    cached_data = get_from_cache(cache_key)
    if cached_data is not None:
        return Response(cached_data)

    centres = get_centres_for_user(request.user)

    city = request.query_params.get("city")
    if city:
        centres = centres.filter(city__iexact=city)

    search_text = request.query_params.get("search", "")
    for word in search_text.split():
        centres = centres.filter(Q(name__icontains=word) | Q(address__icontains=word))

    paginator = PageNumberPagination()
    centres_on_this_page = paginator.paginate_queryset(centres, request)
    serializer = DiagnosticCentreSerializer(centres_on_this_page, many=True)
    response = paginator.get_paginated_response(serializer.data)

    save_to_cache(cache_key, response.data)
    return response


def create_centre(request):
    serializer = DiagnosticCentreSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(request=DiagnosticCentreSerializer, responses=DiagnosticCentreDetailSerializer)
@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsStaffOrReadOnly])
def centre_detail(request, centre_id):
    if request.method == "GET":
        return show_centre(request, centre_id)
    if request.method == "DELETE":
        return delete_centre(request, centre_id)
    return update_centre(request, centre_id)


def show_centre(request, centre_id):
    cache_key = make_cache_key(request)
    cached_data = get_from_cache(cache_key)
    if cached_data is not None:
        return Response(cached_data)

    centre = find_centre(request.user, centre_id)
    if centre is None:
        return not_found_response("Centre not found.")

    data = DiagnosticCentreDetailSerializer(centre).data
    save_to_cache(cache_key, data)
    return Response(data)


def update_centre(request, centre_id):
    centre = find_centre(request.user, centre_id)
    if centre is None:
        return not_found_response("Centre not found.")

    is_patch = request.method == "PATCH"
    serializer = DiagnosticCentreSerializer(centre, data=request.data, partial=is_patch)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response(serializer.data)


def delete_centre(request, centre_id):
    centre = find_centre(request.user, centre_id)
    if centre is None:
        return not_found_response("Centre not found.")

    centre.is_active = False
    centre.save()
    return Response(status=status.HTTP_204_NO_CONTENT)


def get_tests_for_user(user):
    if user.is_staff:
        return DiagnosticTest.objects.all()
    return DiagnosticTest.objects.filter(is_active=True)


def find_test(user, test_id):
    try:
        return get_tests_for_user(user).get(id=test_id)
    except DiagnosticTest.DoesNotExist:
        return None


@extend_schema(methods=["GET"], responses=DiagnosticTestSerializer(many=True))
@extend_schema(methods=["POST"], request=DiagnosticTestSerializer, responses={201: DiagnosticTestSerializer})
@api_view(["GET", "POST"])
@permission_classes([IsStaffOrReadOnly])
def test_list(request):
    if request.method == "POST":
        return create_test(request)
    return list_tests(request)


def list_tests(request):
    cache_key = make_cache_key(request)
    cached_data = get_from_cache(cache_key)
    if cached_data is not None:
        return Response(cached_data)

    tests = get_tests_for_user(request.user)

    search_text = request.query_params.get("search", "")
    for word in search_text.split():
        tests = tests.filter(Q(name__icontains=word) | Q(sample_type__icontains=word))

    paginator = PageNumberPagination()
    tests_on_this_page = paginator.paginate_queryset(tests, request)
    serializer = DiagnosticTestSerializer(tests_on_this_page, many=True)
    response = paginator.get_paginated_response(serializer.data)

    save_to_cache(cache_key, response.data)
    return response


def create_test(request):
    serializer = DiagnosticTestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(request=DiagnosticTestSerializer, responses=DiagnosticTestSerializer)
@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsStaffOrReadOnly])
def test_detail(request, test_id):
    if request.method == "GET":
        return show_test(request, test_id)
    if request.method == "DELETE":
        return delete_test(request, test_id)
    return update_test(request, test_id)


def show_test(request, test_id):
    cache_key = make_cache_key(request)
    cached_data = get_from_cache(cache_key)
    if cached_data is not None:
        return Response(cached_data)

    test = find_test(request.user, test_id)
    if test is None:
        return not_found_response("Test not found.")

    data = DiagnosticTestSerializer(test).data
    save_to_cache(cache_key, data)
    return Response(data)


def update_test(request, test_id):
    test = find_test(request.user, test_id)
    if test is None:
        return not_found_response("Test not found.")

    is_patch = request.method == "PATCH"
    serializer = DiagnosticTestSerializer(test, data=request.data, partial=is_patch)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response(serializer.data)


def delete_test(request, test_id):
    test = find_test(request.user, test_id)
    if test is None:
        return not_found_response("Test not found.")

    test.is_active = False
    test.save()
    return Response(status=status.HTTP_204_NO_CONTENT)


def get_offerings_for_user(user):
    offerings = CentreTest.objects.select_related("centre", "test")
    if user.is_staff:
        return offerings
    return offerings.filter(is_available=True, centre__is_active=True, test__is_active=True)


def find_offering(user, offering_id):
    try:
        return get_offerings_for_user(user).get(id=offering_id)
    except CentreTest.DoesNotExist:
        return None


@extend_schema(methods=["GET"], responses=CentreTestSerializer(many=True))
@extend_schema(methods=["POST"], request=CentreTestSerializer, responses={201: CentreTestSerializer})
@api_view(["GET", "POST"])
@permission_classes([IsStaffOrReadOnly])
def centre_test_list(request):
    if request.method == "POST":
        return create_offering(request)
    return list_offerings(request)


def list_offerings(request):
    cache_key = make_cache_key(request)
    cached_data = get_from_cache(cache_key)
    if cached_data is not None:
        return Response(cached_data)

    offerings = get_offerings_for_user(request.user)

    centre_id = request.query_params.get("centre", "")
    if centre_id.isdigit():
        offerings = offerings.filter(centre_id=centre_id)

    test_id = request.query_params.get("test", "")
    if test_id.isdigit():
        offerings = offerings.filter(test_id=test_id)

    paginator = PageNumberPagination()
    offerings_on_this_page = paginator.paginate_queryset(offerings, request)
    serializer = CentreTestSerializer(offerings_on_this_page, many=True)
    response = paginator.get_paginated_response(serializer.data)

    save_to_cache(cache_key, response.data)
    return response


def create_offering(request):
    serializer = CentreTestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(request=CentreTestSerializer, responses=CentreTestSerializer)
@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsStaffOrReadOnly])
def centre_test_detail(request, offering_id):
    if request.method == "GET":
        return show_offering(request, offering_id)
    if request.method == "DELETE":
        return delete_offering(request, offering_id)
    return update_offering(request, offering_id)


def show_offering(request, offering_id):
    cache_key = make_cache_key(request)
    cached_data = get_from_cache(cache_key)
    if cached_data is not None:
        return Response(cached_data)

    offering = find_offering(request.user, offering_id)
    if offering is None:
        return not_found_response("Offering not found.")

    data = CentreTestSerializer(offering).data
    save_to_cache(cache_key, data)
    return Response(data)


def update_offering(request, offering_id):
    offering = find_offering(request.user, offering_id)
    if offering is None:
        return not_found_response("Offering not found.")

    is_patch = request.method == "PATCH"
    serializer = CentreTestSerializer(offering, data=request.data, partial=is_patch)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response(serializer.data)


def delete_offering(request, offering_id):
    offering = find_offering(request.user, offering_id)
    if offering is None:
        return not_found_response("Offering not found.")

    offering.is_available = False
    offering.save()
    return Response(status=status.HTTP_204_NO_CONTENT)
