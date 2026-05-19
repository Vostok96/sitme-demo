from django.conf import settings


class SecurityHeadersMiddleware:
    """
    Agrega cabeceras defensivas que no siempre vienen configuradas
    desde el hosting o el proxy reverso.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response.setdefault(
            "X-Frame-Options",
            settings.X_FRAME_OPTIONS,
        )
        response.setdefault(
            "X-Content-Type-Options",
            "nosniff",
        )
        response.setdefault(
            "Referrer-Policy",
            settings.SECURE_REFERRER_POLICY,
        )
        response.setdefault(
            "Content-Security-Policy",
            settings.CONTENT_SECURITY_POLICY,
        )
        response.setdefault(
            "Permissions-Policy",
            settings.PERMISSIONS_POLICY,
        )
        response.setdefault(
            "Cross-Origin-Opener-Policy",
            settings.SECURE_CROSS_ORIGIN_OPENER_POLICY,
        )
        response.setdefault(
            "Cross-Origin-Resource-Policy",
            settings.SECURE_CROSS_ORIGIN_RESOURCE_POLICY,
        )
        return response
