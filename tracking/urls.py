from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("nueva-solicitud/", views.crear_orden, name="crear_orden"),
    path(
        "login/",
        views.SITMELoginView.as_view(),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="dashboard"), name="logout"),
    path("cambiar-estado/<int:orden_id>/", views.cambiar_estado, name="cambiar_estado"),
    path("subir-resultado/<int:orden_id>/", views.subir_resultado, name="subir_resultado"),
    path(
        "descargar-resultado/<int:orden_id>/",
        views.descargar_resultado,
        name="descargar_resultado",
    ),
    path("editar-solicitud/<int:orden_id>/", views.editar_orden, name="editar_orden"),
    path("eliminar-solicitud/<int:orden_id>/", views.eliminar_orden, name="eliminar_orden"),
    path("estadisticas/", views.estadisticas, name="estadisticas"),
    path("usuarios/", views.gestionar_usuarios, name="gestionar_usuarios"),
]
