import json
import urllib.error
import urllib.request
import uuid

from django.core.management.base import BaseCommand

from payments.webhooks import SIGNATURE_HEADER, sign


class Command(BaseCommand):
    help = "Send a signed payment webhook to the API (simulated provider)."

    def add_arguments(self, parser):
        parser.add_argument("provider_reference")
        parser.add_argument("result", choices=["succeeded", "failed"])
        parser.add_argument("--event-id", default=None, help="Defaults to a random id.")
        parser.add_argument("--url", default="http://127.0.0.1:8000/api/payments/webhook/")
        parser.add_argument("--bad-signature", action="store_true", help="Send a wrong signature.")

    def handle(self, *args, **opts):
        payload = {
            "event_id": opts["event_id"] or f"evt_{uuid.uuid4().hex[:12]}",
            "type": f"payment.{opts['result']}",
            "data": {"provider_reference": opts["provider_reference"]},
        }
        if opts["result"] == "failed":
            payload["data"]["failure_reason"] = "Insufficient funds (simulated)."

        body = json.dumps(payload).encode()
        signature = "invalid" if opts["bad_signature"] else sign(body)

        request = urllib.request.Request(
            opts["url"], data=body, method="POST",
            headers={"Content-Type": "application/json", SIGNATURE_HEADER: signature},
        )
        try:
            with urllib.request.urlopen(request) as response:
                code, text = response.status, response.read().decode()
        except urllib.error.HTTPError as err:
            code, text = err.code, err.read().decode()

        self.stdout.write(f"event_id={payload['event_id']} -> HTTP {code}: {text}")
