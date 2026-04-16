from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import CatalogoExamen, OrdenExamen


MAX_RESULTADO_MB = 10

class OrdenExamenForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = CatalogoExamen.objects.filter(activo=True)

        if self.instance.pk and self.instance.tipo_examen_id:
            queryset = CatalogoExamen.objects.filter(
                Q(activo=True) | Q(pk=self.instance.tipo_examen_id)
            )

        self.fields['tipo_examen'].queryset = queryset.order_by('nombre')

    class Meta:
        model = OrdenExamen
        # Solo pedimos estos datos al médico. El 'estado' empieza en 'SOLICITADO' por defecto.
        fields = ['paciente_nombre', 'cama', 'tipo_examen', 'notas']
        
        # Le agregamos las clases de Bootstrap para que se vea profesional automáticamente
        widgets = {
            'paciente_nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Juan Pérez'}),
            'cama': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Pediatría - Cama 4'}),
            'tipo_examen': forms.Select(attrs={'class': 'form-select'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Justificación o detalle clínico...'}),
        }

        # NUEVO FORMULARIO: Solo para que el Laboratorio suba el PDF
class SubirResultadoForm(forms.ModelForm):
    def clean_archivo_resultado(self):
        archivo = self.cleaned_data.get('archivo_resultado')

        if not archivo:
            return archivo

        content_type = getattr(archivo, 'content_type', '')
        if content_type and content_type != 'application/pdf':
            raise ValidationError('Solo se permiten archivos PDF.')

        if not archivo.name.lower().endswith('.pdf'):
            raise ValidationError('El archivo debe tener extension .pdf.')

        if archivo.size > MAX_RESULTADO_MB * 1024 * 1024:
            raise ValidationError(
                f'El PDF supera el limite de {MAX_RESULTADO_MB} MB.'
            )

        return archivo

    class Meta:
        model = OrdenExamen
        fields = ['archivo_resultado']
        widgets = {
            'archivo_resultado': forms.FileInput(attrs={'class': 'form-control'})
        }
