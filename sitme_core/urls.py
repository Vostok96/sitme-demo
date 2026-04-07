from django.contrib import admin
from django.urls import path, include
from django.conf import settings # <-- NUEVO
from django.conf.urls.static import static # <-- NUEVO

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('tracking.urls')),
]

# Esto permite abrir los PDFs mientras estamos programando
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

