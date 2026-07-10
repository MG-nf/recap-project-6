from rest_framework.throttling import ScopedRateThrottle


class AuthRateThrottle(ScopedRateThrottle):
    """Always throttle by client IP, never by request.user.

    The stock ScopedRateThrottle keys on request.user.pk once a session is
    authenticated. On signup/login endpoints that's the wrong identity to key
    on: SignUpView logs the caller in on success, and a client can already be
    authenticated as *someone* when hitting /login/. Either case would hand a
    fresh, unthrottled bucket to every new identity, defeating the point of
    rate-limiting these endpoints (mass account creation / credential
    stuffing from one client).
    """

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
