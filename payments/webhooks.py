import hashlib
import hmac

from django.conf import settings

from .models import Payment

SIGNATURE_HEADER = "X-Webhook-Signature"

EVENT_TO_PAYMENT_STATUS = {
    "payment.succeeded": Payment.Status.SUCCESS,
    "payment.failed": Payment.Status.FAILED,
}


def sign(body: bytes) -> str:
    return hmac.new(settings.WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def is_valid_signature(body: bytes, signature: str) -> bool:
    if not signature:
        return False
    # Constant-time comparison, so the signature can't be guessed by timing.
    return hmac.compare_digest(sign(body), signature)
