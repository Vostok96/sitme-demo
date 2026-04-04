from django.contrib import admin
from .models import OrdenExamen, CatalogoExamen

# Registramos el nuevo catálogo
@admin.register(CatalogoExamen)
class CatalogoExamenAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')
    list_editable = ('activo',)
    search_fields = ('nombre',)

@admin.register(OrdenExamen)
class OrdenExamenAdmin(admin.ModelAdmin):
    list_display = ('paciente_nombre', 'tipo_examen', 'estado', 'cama', 'medico_solicitante', 'fecha_solicitud')
    list_filter = ('estado', 'tipo_examen', 'fecha_solicitud')
    search_fields = ('paciente_nombre', 'cama')
    list_editable = ('estado',)