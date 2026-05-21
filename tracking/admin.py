from django.contrib import admin

from .models import CatalogoExamen, EventoOrden, IntentoLogin, OrdenExamen


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
    list_display = (
        'paciente_nombre',
        'tipo_examen',
        'estado',
        'eliminado',
        'fecha_solicitud',
        'medico_solicitante',
        'usuario_eliminacion',
    )
    list_filter = ('estado', 'eliminado', 'tipo_examen', 'fecha_solicitud', 'fecha_eliminacion')
    search_fields = ('paciente_nombre', 'cama', 'tipo_examen__nombre', 'motivo_eliminacion')
    readonly_fields = ('fecha_eliminacion', 'usuario_eliminacion', 'motivo_eliminacion')
    inlines = [EventoOrdenInline]


@admin.register(EventoOrden)
class EventoOrdenAdmin(admin.ModelAdmin):
    list_display = ('orden', 'tipo_evento', 'estado_anterior', 'estado_nuevo', 'usuario', 'fecha_evento')
    list_filter = ('tipo_evento', 'estado_nuevo', 'fecha_evento')
    search_fields = ('orden__paciente_nombre', 'descripcion', 'usuario__username')


@admin.register(IntentoLogin)
class IntentoLoginAdmin(admin.ModelAdmin):
    list_display = ('username', 'ip_address', 'intentos_fallidos', 'bloqueado_hasta', 'ultimo_intento')
    list_filter = ('bloqueado_hasta', 'ultimo_intento')
    search_fields = ('username', 'ip_address', 'identificador')
    readonly_fields = ('identificador', 'username', 'ip_address', 'ultimo_intento', 'creado')
