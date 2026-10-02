from django.core.cache import cache

# Versioned keys: every key contains a version number ("centres:v7:/api/centres/?city=Delhi").
# Any change to centre data bumps the version (signals.py), so old entries are
# never read again and simply expire.
VERSION_KEY = "centres:cache_version"
CACHE_TTL_SECONDS = 10 * 60


def get_version():
    return cache.get_or_set(VERSION_KEY, 1, timeout=None)


def bump_version():
    try:
        cache.incr(VERSION_KEY)
    except ValueError:
        # incr() fails if the key is missing (e.g. Redis was flushed).
        cache.set(VERSION_KEY, 1, timeout=None)


def make_cache_key(request):
    # Staff can see inactive rows, so their responses must never be cached.
    if request.user.is_staff:
        return None
    return f"centres:v{get_version()}:{request.get_full_path()}"


def get_from_cache(cache_key):
    if cache_key is None:
        return None
    return cache.get(cache_key)


def save_to_cache(cache_key, data):
    if cache_key is None:
        return
    cache.set(cache_key, data, CACHE_TTL_SECONDS)
