from django.db import models


class DiagnosticCentre(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=500)
    city = models.CharField(max_length=100, db_index=True)
    pincode = models.CharField(max_length=10, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            # A chain can have several branches in a city, but not two at the same address.
            models.UniqueConstraint(fields=["name", "city", "address"], name="unique_centre_per_address"),
        ]

    def __str__(self):
        return f"{self.name} ({self.city})"


class DiagnosticTest(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    sample_type = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CentreTest(models.Model):
    # Price lives here, not on DiagnosticTest, because each centre sets its own price.
    centre = models.ForeignKey(DiagnosticCentre, on_delete=models.CASCADE, related_name="offerings")
    test = models.ForeignKey(DiagnosticTest, on_delete=models.CASCADE, related_name="offerings")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["centre_id", "test__name"]
        constraints = [
            models.UniqueConstraint(fields=["centre", "test"], name="unique_test_per_centre"),
            models.CheckConstraint(condition=models.Q(price__gt=0), name="centre_test_price_positive"),
        ]

    def __str__(self):
        return f"{self.test.name} @ {self.centre.name}: {self.price}"
