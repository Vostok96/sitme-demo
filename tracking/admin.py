from django.contrib import admin

from .models import CatalogoExamen, EventoOrden, OrdenExamen


@admin.register(CatalogoExamen)
class CatalogoExamenAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)
    ordering = ('nombre',)


class EventoOrdenInline(admin.TabularInline):
    model = EventoOrden
    extra = 0
    can_delete = False
    fields = ('fecha_evento', 'tipo_evento', 'descripcion', 'estado_anterior', 'estado_nuevo', 'usuario')
    readonly_fields = fields
    ordering = ('-fecha_evento', '-id')


@admin.register(OrdenExamen)
class OrdenExamenAdmin(admin.ModelAdmin):
    list_display = ('paciente_nombre', 'tipo_examen', 'estado', 'fecha_solicitud', 'medico_solicitante')
    list_filter = ('estado', 'tipo_examen', 'fecha_solicitud')
    search_fields = ('paciente_nombre', 'cama', 'tipo_examen__nombre')
    inlines = [EventoOrdenInline]


@admin.register(EventoOrden)
class EventoOrdenAdmin(admin.ModelAdmin):
    list_display = ('orden', 'tipo_evento', 'estado_anterior', 'estado_nuevo', 'usuario', 'fecha_evento')
    list_filter = ('tipo_evento', 'estado_nuevo', 'fecha_evento')
    search_fields = ('orden__paciente_nombre', 'descripcion', 'usuario__username')
