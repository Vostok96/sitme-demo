from django.urls import path
from django.contrib.auth import views as auth_views # <-- NUEVO IMPORT
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('nueva-solicitud/', views.crear_orden, name='crear_orden'),
    path('login/', auth_views.LoginView.as_view(template_name='tracking/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='dashboard'), name='logout'),
    
    # NUEVA RUTA PARA EL CAMBIO DE ESTADO
    path('cambiar-estado/<int:orden_id>/', views.cambiar_estado, name='cambiar_estado'),
    # NUEVA RUTA PARA SUBIR RESULTADOS
    path('subir-resultado/<int:orden_id>/', views.subir_resultado, name='subir_resultado'),
    path('editar-solicitud/<int:orden_id>/', views.editar_orden, name='editar_orden'),
    path('estadisticas/', views.estadisticas, name='estadisticas'),
    path('usuarios/', views.gestionar_usuarios, name='gestionar_usuarios'),
]
