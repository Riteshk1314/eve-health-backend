import logging
import time
import uuid

logger = logging.getLogger("requests")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        started = time.monotonic()

        response = self.get_response(request)

        user = getattr(request, "user", None)
        logger.info(
            "http_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
                "user_id": user.id if user is not None and user.is_authenticated else None,
            },
        )
        response["X-Request-ID"] = request_id
        return response
