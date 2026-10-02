from rest_framework.throttling import SimpleRateThrottle


class RateLimitPerUserOrIP(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            who = request.user.pk
        else:
            who = self.get_ident(request)
        return f"throttle_{self.scope}_{who}"


class AuthThrottle(RateLimitPerUserOrIP):
    scope = "auth"


class PaymentThrottle(RateLimitPerUserOrIP):
    scope = "payments"

    def get_cache_key(self, request, view):
        # Only creating payments is limited; reading them is not.
        if request.method != "POST":
            return None
        return super().get_cache_key(request, view)
