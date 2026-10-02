from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import bump_version
from .models import CentreTest, DiagnosticCentre, DiagnosticTest


@receiver([post_save, post_delete], sender=DiagnosticCentre)
@receiver([post_save, post_delete], sender=DiagnosticTest)
@receiver([post_save, post_delete], sender=CentreTest)
def invalidate_centre_cache(**kwargs):
    bump_version()
