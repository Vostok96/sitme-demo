from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import OrdenExamenForm, SubirResultadoForm
from .models import CatalogoExamen, EventoOrden, OrdenExamen
from .permissions import GRUPO_EPIDEMIOLOGIA, GRUPO_LABORATORIO


class TrackingFlowTests(TestCase):
    def setUp(self):
        self.group_lab, _ = Group.objects.get_or_create(name=GRUPO_LABORATORIO)
        self.group_epi, _ = Group.objects.get_or_create(name=GRUPO_EPIDEMIOLOGIA)

        self.staff = User.objects.create_user(
            username='laboratorio',
            password='demo12345',
            first_name='Lab',
        )
        self.staff.groups.add(self.group_lab)

        self.medico = User.objects.create_user(
            username='medicina',
            password='demo12345',
            first_name='Medico',
        )
        self.epidemiologia = User.objects.create_user(
            username='epi',
            password='demo12345',
            first_name='Epi',
        )
        self.epidemiologia.groups.add(self.group_epi)

        self.examen_activo = CatalogoExamen.objects.create(nombre='PCR Dengue', activo=True)
        self.examen_inactivo = CatalogoExamen.objects.create(nombre='Cultivo Antiguo', activo=False)
        self.orden = OrdenExamen.objects.create(
            paciente_nombre='Paciente Demo',
            cama='Emergencia 1',
            tipo_examen=self.examen_activo,
            medico_solicitante=self.medico,
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_form_solo_muestra_examenes_activos(self):
        form = OrdenExamenForm()
        self.assertQuerySetEqual(
            form.fields['tipo_examen'].queryset,
            [self.examen_activo],
            transform=lambda examen: examen,
        )

    def test_crear_orden_asigna_medico_y_evento(self):
        self.client.login(username='medicina', password='demo12345')
        response = self.client.post(
            reverse('crear_orden'),
            {
                'paciente_nombre': 'Ana Torres',
                'cama': 'UCI 2',
                'tipo_examen': self.examen_activo.id,
                'notas': 'Control',
            },
        )
        self.assertEqual(response.status_code, 302)
        orden = OrdenExamen.objects.get(paciente_nombre='Ana Torres')
        self.assertEqual(orden.medico_solicitante, self.medico)
        self.assertEqual(orden.estado, 'SOLICITADO')
        self.assertTrue(
            EventoOrden.objects.filter(
                orden=orden,
                tipo_evento='CREACION',
                estado_nuevo='SOLICITADO',
            ).exists()
        )

    def test_cambiar_estado_registra_usuario_fecha_y_evento(self):
        self.client.login(username='laboratorio', password='demo12345')
        response = self.client.post(
            reverse('cambiar_estado', args=[self.orden.id]),
            {'nuevo_estado': 'TOMADO'},
        )
        self.assertEqual(response.status_code, 302)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'TOMADO')
        self.assertEqual(self.orden.laboratorista_toma, self.staff)
        self.assertIsNotNone(self.orden.fecha_toma)
        self.assertLessEqual(self.orden.fecha_toma, timezone.now())
        self.assertTrue(
            EventoOrden.objects.filter(
                orden=self.orden,
                tipo_evento='CAMBIO_ESTADO',
                estado_anterior='SOLICITADO',
                estado_nuevo='TOMADO',
                usuario=self.staff,
            ).exists()
        )

    def test_subir_resultado_rechaza_archivos_no_pdf(self):
        archivo = SimpleUploadedFile(
            'resultado.txt',
            b'no es pdf',
            content_type='text/plain',
        )
        form = SubirResultadoForm(
            data={},
            files={'archivo_resultado': archivo},
            instance=self.orden,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('archivo_resultado', form.errors)

    def test_epidemiologia_puede_ver_reportes_y_no_crear_ordenes(self):
        self.client.login(username='epi', password='demo12345')
        response_reportes = self.client.get(reverse('estadisticas'))
        self.assertEqual(response_reportes.status_code, 200)

        response_creacion = self.client.get(reverse('crear_orden'))
        self.assertEqual(response_creacion.status_code, 302)
        self.assertEqual(OrdenExamen.objects.count(), 1)
