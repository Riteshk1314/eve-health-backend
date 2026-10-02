from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import CentreTest, DiagnosticCentre, DiagnosticTest


class DiagnosticTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosticTest
        fields = ["id", "name", "description", "sample_type", "is_active"]


class DiagnosticCentreSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosticCentre
        fields = ["id", "name", "address", "city", "pincode", "is_active"]


class CentreTestSerializer(serializers.ModelSerializer):
    centre_name = serializers.CharField(source="centre.name", read_only=True)
    test_name = serializers.CharField(source="test.name", read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = CentreTest
        fields = ["id", "centre", "centre_name", "test", "test_name", "price", "is_available"]


class OfferedTestSerializer(serializers.ModelSerializer):
    test_id = serializers.IntegerField(source="test.id", read_only=True)
    test_name = serializers.CharField(source="test.name", read_only=True)
    sample_type = serializers.CharField(source="test.sample_type", read_only=True)

    class Meta:
        model = CentreTest
        fields = ["id", "test_id", "test_name", "sample_type", "price"]


class DiagnosticCentreDetailSerializer(serializers.ModelSerializer):
    tests = serializers.SerializerMethodField()

    class Meta:
        model = DiagnosticCentre
        fields = ["id", "name", "address", "city", "pincode", "is_active", "tests"]

    @extend_schema_field(OfferedTestSerializer(many=True))
    def get_tests(self, centre):
        offerings = centre.offerings.filter(
            is_available=True,
            test__is_active=True,
        ).select_related("test")
        return OfferedTestSerializer(offerings, many=True).data
