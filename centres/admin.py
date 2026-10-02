from django.contrib import admin

from .models import CentreTest, DiagnosticCentre, DiagnosticTest


class CentreTestInline(admin.TabularInline):
    model = CentreTest
    extra = 1


@admin.register(DiagnosticCentre)
class DiagnosticCentreAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "is_active"]
    list_filter = ["city", "is_active"]
    search_fields = ["name", "address"]
    inlines = [CentreTestInline]


@admin.register(DiagnosticTest)
class DiagnosticTestAdmin(admin.ModelAdmin):
    list_display = ["name", "sample_type", "is_active"]
    search_fields = ["name"]
