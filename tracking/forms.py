from django import forms
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import CatalogoExamen, OrdenExamen
from .permissions import GRUPO_EPIDEMIOLOGIA, GRUPO_LABORATORIO, GRUPO_MEDICO


MAX_RESULTADO_MB = 10

ROL_CHOICES = [
    (GRUPO_MEDICO, 'Medico / Servicio'),
    (GRUPO_LABORATORIO, 'Laboratorio'),
    (GRUPO_EPIDEMIOLOGIA, 'Epidemiologia'),
]


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
        fields = ['paciente_nombre', 'cama', 'tipo_examen', 'notas']
        widgets = {
            'paciente_nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Juan Perez'}),
            'cama': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Pediatria - Cama 4'}),
            'tipo_examen': forms.Select(attrs={'class': 'form-select'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Justificacion o detalle clinico...'}),
        }


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


class CrearUsuarioSITMEForm(forms.ModelForm):
    rol = forms.ChoiceField(
        choices=ROL_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    password = forms.CharField(
        required=False,
        help_text='Si lo dejas vacio, SITME generara una contrasena temporal segura.',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dejar vacio para generar automaticamente'}),
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. uci o nombre.apellido'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre visible del servicio o persona'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Opcional'}),
        }

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('Ese usuario ya existe.')
        return username

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.username = self.cleaned_data['username'].strip()
        usuario.email = self.cleaned_data.get('email', '').strip()
        usuario.is_staff = self.cleaned_data['rol'] == GRUPO_LABORATORIO
        usuario.is_superuser = False

        if commit:
            usuario.save()
            self._asignar_grupo(usuario)

        return usuario

    def _asignar_grupo(self, usuario):
        Group.objects.get_or_create(name=GRUPO_LABORATORIO)
        Group.objects.get_or_create(name=GRUPO_EPIDEMIOLOGIA)
        Group.objects.get_or_create(name=GRUPO_MEDICO)
        usuario.groups.clear()
        usuario.groups.add(Group.objects.get(name=self.cleaned_data['rol']))


class ResetPasswordUsuarioForm(forms.Form):
    usuario_id = forms.IntegerField(widget=forms.HiddenInput())
