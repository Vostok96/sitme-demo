from django import forms
from .models import OrdenExamen

class OrdenExamenForm(forms.ModelForm):
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
    class Meta:
        model = OrdenExamen
        fields = ['archivo_resultado']
        widgets = {
            'archivo_resultado': forms.FileInput(attrs={'class': 'form-control'})
        }