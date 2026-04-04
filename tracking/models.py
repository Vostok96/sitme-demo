from django.db import models
from django.contrib.auth.models import User

# NUEVO: Tabla para gestionar los exámenes dinámicamente
class CatalogoExamen(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Examen")
    activo = models.BooleanField(default=True, verbose_name="¿Disponible para solicitar?")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Catálogo de Examen"
        verbose_name_plural = "Catálogo de Exámenes"
        ordering = ['nombre']

class OrdenExamen(models.Model):
    ESTADO_CHOICES = [
        ('SOLICITADO', '🔴 Pendiente / Solicitado'),
        ('TOMADO', '🟡 Muestra Tomada'),
        ('ENVIADO', '🔵 Enviado a LIMA/DIRESA'),
        ('RESULTADO', '🟢 Resultado Recibido'),
    ]

    paciente_nombre = models.CharField(max_length=200, verbose_name="Nombre del Paciente")
    cama = models.CharField(max_length=50, verbose_name="Cama / Servicio")

   # NUEVO CAMPO: Para subir el PDF del resultado
    archivo_resultado = models.FileField(upload_to='resultados_pdf/', blank=True, null=True, verbose_name="PDF del Resultado")

    def __str__(self):
        return f"{self.paciente_nombre} - {self.tipo_examen.nombre} - {self.estado}"
    
    # MODIFICADO: Ahora se conecta al catálogo en lugar de una lista fija
    tipo_examen = models.ForeignKey(CatalogoExamen, on_delete=models.RESTRICT, verbose_name="Tipo de Examen")
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='SOLICITADO', verbose_name="Estado de la Muestra")
    medico_solicitante = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Médico Solicitante")
    fecha_solicitud = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora de Solicitud")
    notas = models.TextField(blank=True, null=True, verbose_name="Observaciones / Justificación")

    def __str__(self):
        return f"{self.paciente_nombre} - {self.tipo_examen.nombre} - {self.estado}"

    class Meta:
        verbose_name = "Orden de Examen"
        verbose_name_plural = "Órdenes de Exámenes"
        ordering = ['-fecha_solicitud']