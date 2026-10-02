from decimal import Decimal

from django.core.management.base import BaseCommand

from centres.models import CentreTest, DiagnosticCentre, DiagnosticTest

TESTS = [
    ("Complete Blood Count", "blood"),
    ("Lipid Profile", "blood"),
    ("Thyroid Profile (T3, T4, TSH)", "blood"),
    ("HbA1c", "blood"),
    ("Urine Routine", "urine"),
    ("Chest X-Ray", "imaging"),
]

CENTRES = [
    ("EVE Diagnostics Saket", "A-12, Saket", "Delhi", "110017",
     {"Complete Blood Count": "350", "Lipid Profile": "600", "HbA1c": "450", "Chest X-Ray": "800"}),
    ("EVE Diagnostics Koramangala", "80 Feet Rd, Koramangala", "Bengaluru", "560034",
     {"Complete Blood Count": "300", "Thyroid Profile (T3, T4, TSH)": "550", "Urine Routine": "200"}),
    ("CityLab Andheri", "Link Rd, Andheri West", "Mumbai", "400053",
     {"Complete Blood Count": "400", "Lipid Profile": "650", "Chest X-Ray": "900"}),
]


class Command(BaseCommand):
    help = "Seed sample diagnostic centres, tests and prices."

    def handle(self, *args, **options):
        tests = {}
        for name, sample_type in TESTS:
            tests[name], _ = DiagnosticTest.objects.get_or_create(
                name=name, defaults={"sample_type": sample_type}
            )

        for name, address, city, pincode, prices in CENTRES:
            centre, _ = DiagnosticCentre.objects.get_or_create(
                name=name, city=city, defaults={"address": address, "pincode": pincode}
            )
            for test_name, price in prices.items():
                CentreTest.objects.update_or_create(
                    centre=centre, test=tests[test_name], defaults={"price": Decimal(price)}
                )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(TESTS)} tests and {len(CENTRES)} centres."
        ))
