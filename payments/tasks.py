import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from . import services
from .models import WebhookEvent
from .webhooks import EVENT_TO_PAYMENT_STATUS

logger = logging.getLogger(__name__)

MAX_RETRIES = 5


@shared_task(bind=True, max_retries=MAX_RETRIES)
def process_webhook_event(self, event_pk):
    try:
        with transaction.atomic():
            # Lock the event so two workers can't process it at the same time.
            event = WebhookEvent.objects.select_for_update().get(pk=event_pk)
            if event.status == WebhookEvent.Status.PROCESSED:
                logger.info("webhook_already_processed", extra={"event_id": event.event_id})
                return

            event.attempts += 1
            new_status = EVENT_TO_PAYMENT_STATUS[event.event_type]
            reason = event.payload.get("data", {}).get("failure_reason", "")
            services.process_payment(event.payment_id, new_status, reason)

            event.status = WebhookEvent.Status.PROCESSED
            event.processed_at = timezone.now()
            event.last_error = ""
            event.save()

        logger.info("webhook_processed", extra={"event_id": event.event_id, "attempts": event.attempts})

    except Exception as exc:
        # The transaction above rolled back, so record the failed attempt separately.
        event = WebhookEvent.objects.get(pk=event_pk)
        event.attempts += 1
        event.last_error = repr(exc)

        if self.request.retries >= MAX_RETRIES:
            event.status = WebhookEvent.Status.FAILED
            event.save(update_fields=["attempts", "last_error", "status"])
            logger.error("webhook_failed_permanently", extra={"event_id": event.event_id, "error": repr(exc)})
            return

        event.save(update_fields=["attempts", "last_error"])
        delay = 2 ** (self.request.retries + 1)  # 2s, 4s, 8s, 16s, 32s
        logger.warning(
            "webhook_retry_scheduled",
            extra={"event_id": event.event_id, "retry_in_seconds": delay, "error": repr(exc)},
        )
        raise self.retry(exc=exc, countdown=delay)
