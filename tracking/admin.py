from django.contrib import admin
from .models import CatalogoExamen, OrdenExamen

# Esto habilita el Catálogo de Exámenes en el panel
@admin.register(CatalogoExamen)
class CatalogoExamenAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)
    ordering = ('nombre',) # Los ordena alfabéticamente automáticamente

# De paso, habilitamos las Órdenes por si algún día necesitas borrar una de prueba
@admin.register(OrdenExamen)
class OrdenExamenAdmin(admin.ModelAdmin):
    list_display = ('paciente_nombre', 'tipo_examen', 'estado', 'fecha_solicitud')
    list_filter = ('estado', 'fecha_solicitud')
    search_fields = ('paciente_nombre', 'cama')