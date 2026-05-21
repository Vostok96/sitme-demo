from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class CatalogoExamen(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Examen")
    activo = models.BooleanField(default=True, verbose_name="Disponible para solicitar")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Catalogo de Examen"
        verbose_name_plural = "Catalogo de Examenes"
        ordering = ['nombre']


class OrdenExamen(models.Model):
    ESTADO_CHOICES = [
        ('SOLICITADO', 'Pendiente / Solicitado'),
        ('TOMADO', 'Muestra Tomada'),
        ('ENVIADO', 'Enviado a LIMA/DIRESA'),
        ('RESULTADO', 'Resultado Recibido'),
    ]

    paciente_nombre = models.CharField(max_length=200, verbose_name="Nombre del Paciente")
    cama = models.CharField(max_length=50, verbose_name="Cama / Servicio")
    archivo_resultado = models.FileField(
        upload_to='resultados_pdf/',
        blank=True,
        null=True,
        verbose_name="PDF del Resultado",
    )
    tipo_examen = models.ForeignKey(
        CatalogoExamen,
        on_delete=models.RESTRICT,
        verbose_name="Tipo de Examen",
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='SOLICITADO',
        verbose_name="Estado de la Muestra",
    )
    medico_solicitante = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Medico Solicitante",
    )
    fecha_solicitud = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y Hora de Solicitud",
    )
    fecha_toma = models.DateTimeField(blank=True, null=True, verbose_name="Fecha y Hora de Toma")
    fecha_envio = models.DateTimeField(blank=True, null=True, verbose_name="Fecha y Hora de Envio")
    fecha_resultado = models.DateTimeField(blank=True, null=True, verbose_name="Fecha y Hora de Resultado")
    notas = models.TextField(blank=True, null=True, verbose_name="Observaciones / Justificacion")
    eliminado = models.BooleanField(default=False, verbose_name="Eliminado del tablero")
    fecha_eliminacion = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha y Hora de Eliminacion",
    )
    usuario_eliminacion = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes_eliminadas',
        verbose_name="Usuario que Elimino",
    )
    motivo_eliminacion = models.TextField(blank=True, verbose_name="Motivo de Eliminacion")
    laboratorista_toma = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tomas_realizadas',
    )
    laboratorista_envio = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='envios_realizados',
    )
    laboratorista_resultado = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resultados_subidos',
    )

    def __str__(self):
        return f"{self.paciente_nombre} - {self.tipo_examen.nombre} - {self.estado}"

    class Meta:
        verbose_name = "Orden de Examen"
        verbose_name_plural = "Ordenes de Examenes"
        ordering = ['-fecha_solicitud']


class EventoOrden(models.Model):
    TIPO_CHOICES = [
        ('CREACION', 'Creacion'),
        ('EDICION', 'Edicion'),
        ('CAMBIO_ESTADO', 'Cambio de Estado'),
        ('PDF', 'Resultado PDF'),
        ('DESCARGA_PDF', 'Descarga de PDF'),
        ('ELIMINACION', 'Eliminacion'),
    ]

    orden = models.ForeignKey(OrdenExamen, on_delete=models.CASCADE, related_name='eventos')
    tipo_evento = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo de Evento")
    descripcion = models.CharField(max_length=255, verbose_name="Descripcion")
    estado_anterior = models.CharField(max_length=20, blank=True, null=True, verbose_name="Estado Anterior")
    estado_nuevo = models.CharField(max_length=20, blank=True, null=True, verbose_name="Estado Nuevo")
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="Usuario Responsable",
    )
    fecha_evento = models.DateTimeField(auto_now_add=True, verbose_name="Fecha del Evento")

    def __str__(self):
        return f"{self.orden_id} - {self.tipo_evento} - {self.fecha_evento:%Y-%m-%d %H:%M}"

    class Meta:
        verbose_name = "Evento de Orden"
        verbose_name_plural = "Eventos de Orden"
        ordering = ['-fecha_evento', '-id']


class AuditoriaUsuario(models.Model):
    TIPO_CHOICES = [
        ('CREACION_USUARIO', 'Creacion de usuario'),
        ('RESET_PASSWORD', 'Reset de contrasena'),
    ]

    tipo_evento = models.CharField(
        max_length=30,
        choices=TIPO_CHOICES,
        verbose_name="Tipo de Evento",
    )
    descripcion = models.CharField(max_length=255, verbose_name="Descripcion")
    username_afectado = models.CharField(max_length=150, verbose_name="Usuario Afectado")
    nombre_visible_afectado = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Nombre Visible Afectado",
    )
    rol_asignado = models.CharField(max_length=50, blank=True, verbose_name="Rol Asignado")
    usuario_objetivo = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auditorias_recibidas',
        verbose_name="Usuario Objetivo",
    )
    usuario_responsable = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auditorias_realizadas',
        verbose_name="Usuario Responsable",
    )
    fecha_evento = models.DateTimeField(auto_now_add=True, verbose_name="Fecha del Evento")

    def __str__(self):
        return f"{self.username_afectado} - {self.tipo_evento} - {self.fecha_evento:%Y-%m-%d %H:%M}"

    class Meta:
        verbose_name = "Auditoria de Usuario"
        verbose_name_plural = "Auditoria de Usuarios"
        ordering = ['-fecha_evento', '-id']


class IntentoLogin(models.Model):
    identificador = models.CharField(max_length=255, unique=True)
    username = models.CharField(max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    intentos_fallidos = models.PositiveIntegerField(default=0)
    bloqueado_hasta = models.DateTimeField(blank=True, null=True)
    ultimo_intento = models.DateTimeField(auto_now=True)
    creado = models.DateTimeField(auto_now_add=True)

    def esta_bloqueado(self):
        return bool(self.bloqueado_hasta and self.bloqueado_hasta > timezone.now())

    class Meta:
        verbose_name = "Intento de Login"
        verbose_name_plural = "Intentos de Login"
        ordering = ['-ultimo_intento']
        indexes = [
            models.Index(fields=['username', 'ip_address']),
            models.Index(fields=['bloqueado_hasta']),
        ]
