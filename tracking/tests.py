from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import OrdenExamenForm, SubirResultadoForm
from .models import CatalogoExamen, EventoOrden, IntentoLogin, OrdenExamen
from .permissions import GRUPO_EPIDEMIOLOGIA, GRUPO_LABORATORIO, GRUPO_MEDICO


class TrackingFlowTests(TestCase):
    def setUp(self):
        self.group_lab, _ = Group.objects.get_or_create(name=GRUPO_LABORATORIO)
        self.group_epi, _ = Group.objects.get_or_create(name=GRUPO_EPIDEMIOLOGIA)

        self.staff = User.objects.create_user(
            username="laboratorio",
            password="demo12345",
            first_name="Lab",
        )
        self.staff.groups.add(self.group_lab)

        self.medico = User.objects.create_user(
            username="medicina",
            password="demo12345",
            first_name="Medico",
        )
        self.medico_con_enie = User.objects.create_user(
            username="kpena",
            password="demo12345",
            first_name="Katherine Peña",
        )
        self.epidemiologia = User.objects.create_user(
            username="epi",
            password="demo12345",
            first_name="Epi",
        )
        self.epidemiologia.groups.add(self.group_epi)

        self.examen_activo = CatalogoExamen.objects.create(
            nombre="PCR Dengue", activo=True
        )
        self.examen_inactivo = CatalogoExamen.objects.create(
            nombre="Cultivo Antiguo", activo=False
        )
        self.orden = OrdenExamen.objects.create(
            paciente_nombre="Paciente Demo",
            cama="Emergencia 1",
            tipo_examen=self.examen_activo,
            medico_solicitante=self.medico,
        )
        self.orden_con_enie = OrdenExamen.objects.create(
            paciente_nombre="Richard Enríquez Quiroz",
            cama="Intermedios II",
            tipo_examen=self.examen_activo,
            medico_solicitante=self.medico_con_enie,
            notas="Seguimiento en Niño observado",
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_login_page_renderiza_sin_parametro_next(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ingresar al sistema")

    def test_login_bloquea_intentos_repetidos_por_fuerza_bruta(self):
        for _ in range(5):
            response = self.client.post(
                reverse("login"),
                {"username": "laboratorio", "password": "clave-incorrecta"},
            )
            self.assertEqual(response.status_code, 200)

        intento = IntentoLogin.objects.get(username="laboratorio")
        self.assertTrue(intento.esta_bloqueado())

        response = self.client.post(
            reverse("login"),
            {"username": "laboratorio", "password": "demo12345"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Demasiados intentos fallidos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_correcto_limpia_intentos_fallidos_previos(self):
        IntentoLogin.objects.create(
            identificador="laboratorio|127.0.0.1",
            username="laboratorio",
            ip_address="127.0.0.1",
            intentos_fallidos=2,
        )

        response = self.client.post(
            reverse("login"),
            {"username": "laboratorio", "password": "demo12345"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(IntentoLogin.objects.filter(username="laboratorio").exists())

    def test_form_solo_muestra_examenes_activos(self):
        form = OrdenExamenForm()
        self.assertQuerySetEqual(
            form.fields["tipo_examen"].queryset,
            [self.examen_activo],
            transform=lambda examen: examen,
        )

    def test_crear_orden_asigna_medico_y_evento(self):
        self.client.login(username="medicina", password="demo12345")
        response = self.client.post(
            reverse("crear_orden"),
            {
                "paciente_nombre": "Ana Torres",
                "cama": "UCI 2",
                "tipo_examen": self.examen_activo.id,
                "notas": "Control",
            },
        )
        self.assertEqual(response.status_code, 302)
        orden = OrdenExamen.objects.get(paciente_nombre="Ana Torres")
        self.assertEqual(orden.medico_solicitante, self.medico)
        self.assertEqual(orden.estado, "SOLICITADO")
        self.assertTrue(
            EventoOrden.objects.filter(
                orden=orden,
                tipo_evento="CREACION",
                estado_nuevo="SOLICITADO",
            ).exists()
        )

    def test_cambiar_estado_registra_usuario_fecha_y_evento(self):
        self.client.login(username="laboratorio", password="demo12345")
        response = self.client.post(
            reverse("cambiar_estado", args=[self.orden.id]),
            {"nuevo_estado": "TOMADO"},
        )
        self.assertEqual(response.status_code, 302)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, "TOMADO")
        self.assertEqual(self.orden.laboratorista_toma, self.staff)
        self.assertIsNotNone(self.orden.fecha_toma)
        self.assertLessEqual(self.orden.fecha_toma, timezone.now())
        self.assertTrue(
            EventoOrden.objects.filter(
                orden=self.orden,
                tipo_evento="CAMBIO_ESTADO",
                estado_anterior="SOLICITADO",
                estado_nuevo="TOMADO",
                usuario=self.staff,
            ).exists()
        )

    def test_subir_resultado_rechaza_archivos_no_pdf(self):
        archivo = SimpleUploadedFile(
            "resultado.txt",
            b"no es pdf",
            content_type="text/plain",
        )
        form = SubirResultadoForm(
            data={},
            files={"archivo_resultado": archivo},
            instance=self.orden,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("archivo_resultado", form.errors)

    def test_subir_resultado_actualiza_estado_y_registra_eventos(self):
        self.client.login(username="laboratorio", password="demo12345")
        archivo = SimpleUploadedFile(
            "resultado.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("subir_resultado", args=[self.orden.id]),
            {"archivo_resultado": archivo},
        )
        self.assertEqual(response.status_code, 302)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, "RESULTADO")
        self.assertIsNotNone(self.orden.archivo_resultado)
        self.assertEqual(self.orden.laboratorista_resultado, self.staff)
        self.assertTrue(
            EventoOrden.objects.filter(
                orden=self.orden,
                tipo_evento="PDF",
                usuario=self.staff,
            ).exists()
        )
        self.assertTrue(
            EventoOrden.objects.filter(
                orden=self.orden,
                tipo_evento="CAMBIO_ESTADO",
                estado_nuevo="RESULTADO",
                usuario=self.staff,
            ).exists()
        )

    def test_descargar_resultado_usa_vista_protegida_y_registra_descarga(self):
        self.client.login(username="laboratorio", password="demo12345")
        self.orden.archivo_resultado = SimpleUploadedFile(
            "resultado.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            content_type="application/pdf",
        )
        self.orden.save()

        response = self.client.get(reverse("descargar_resultado", args=[self.orden.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertTrue(
            EventoOrden.objects.filter(
                orden=self.orden,
                tipo_evento="DESCARGA_PDF",
                usuario=self.staff,
            ).exists()
        )

    def test_epidemiologia_puede_ver_reportes_y_no_crear_ordenes(self):
        total_inicial = OrdenExamen.objects.count()
        self.client.login(username="epi", password="demo12345")
        response_reportes = self.client.get(reverse("estadisticas"))
        self.assertEqual(response_reportes.status_code, 200)

        response_creacion = self.client.get(reverse("crear_orden"))
        self.assertEqual(response_creacion.status_code, 302)
        self.assertEqual(OrdenExamen.objects.count(), total_inicial)

    def test_laboratorio_elimina_solicitud_con_auditoria_sin_borrarla(self):
        self.client.login(username="laboratorio", password="demo12345")
        response = self.client.post(
            reverse("eliminar_orden", args=[self.orden.id]),
            {"motivo": "Registro duplicado por error de digitación."},
        )
        self.assertEqual(response.status_code, 302)

        self.orden.refresh_from_db()
        self.assertTrue(self.orden.eliminado)
        self.assertEqual(self.orden.usuario_eliminacion, self.staff)
        self.assertEqual(
            self.orden.motivo_eliminacion,
            "Registro duplicado por error de digitación.",
        )
        self.assertTrue(
            EventoOrden.objects.filter(
                orden=self.orden,
                tipo_evento="ELIMINACION",
                usuario=self.staff,
            ).exists()
        )

        dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotContains(dashboard, "Paciente Demo")

        reportes = self.client.get(reverse("estadisticas"))
        self.assertEqual(reportes.status_code, 200)
        self.assertContains(reportes, "Auditoría de solicitudes retiradas")
        self.assertContains(reportes, "Paciente Demo")

    def test_epidemiologia_no_puede_eliminar_solicitudes(self):
        self.client.login(username="epi", password="demo12345")
        response = self.client.post(
            reverse("eliminar_orden", args=[self.orden.id]),
            {"motivo": "Intento no autorizado"},
        )
        self.assertEqual(response.status_code, 302)
        self.orden.refresh_from_db()
        self.assertFalse(self.orden.eliminado)

    def test_medico_no_puede_eliminar_solicitudes(self):
        self.client.login(username="medicina", password="demo12345")
        response = self.client.post(
            reverse("eliminar_orden", args=[self.orden.id]),
            {"motivo": "No debería poder borrar"},
        )
        self.assertEqual(response.status_code, 302)
        self.orden.refresh_from_db()
        self.assertFalse(self.orden.eliminado)

    def test_laboratorio_puede_crear_usuario_desde_panel(self):
        self.client.login(username="laboratorio", password="demo12345")
        response = self.client.post(
            reverse("gestionar_usuarios"),
            {
                "accion": "crear_usuario",
                "username": "nuevo_servicio",
                "first_name": "Nuevo Servicio",
                "email": "",
                "rol": GRUPO_MEDICO,
                "password": "Temporal123@",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        nuevo_usuario = User.objects.get(username="nuevo_servicio")
        self.assertTrue(nuevo_usuario.check_password("Temporal123@"))
        self.assertTrue(nuevo_usuario.groups.filter(name=GRUPO_MEDICO).exists())

    def test_laboratorio_puede_resetear_password_desde_panel(self):
        self.client.login(username="laboratorio", password="demo12345")
        response = self.client.post(
            reverse("gestionar_usuarios"),
            {
                "accion": "reset_password",
                "usuario_id": self.medico.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.medico.refresh_from_db()
        self.assertContains(response, "Contraseña temporal generada")

    def test_dashboard_busca_por_nombre_visible_del_medico(self):
        self.client.login(username="laboratorio", password="demo12345")
        response = self.client.get(reverse("dashboard"), {"q": "Medico"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paciente Demo")

    def test_dashboard_busca_con_enie_en_nombre_visible(self):
        self.client.login(username="laboratorio", password="demo12345")
        response = self.client.get(reverse("dashboard"), {"q": "ñ"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Richard Enríquez Quiroz")
        self.assertNotContains(response, "Paciente Demo")

    def test_dashboard_busca_sin_tilde_y_encuentra_texto_con_tilde(self):
        self.client.login(username="laboratorio", password="demo12345")
        response = self.client.get(reverse("dashboard"), {"q": "pena"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Richard Enríquez Quiroz")

    def test_dashboard_busca_por_fragmento_interno_de_cualquier_dato(self):
        self.client.login(username="laboratorio", password="demo12345")
        response = self.client.get(reverse("dashboard"), {"q": "ríqu"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Richard Enríquez Quiroz")

    def test_dashboard_renderiza_si_existe_orden_sin_medico(self):
        OrdenExamen.objects.create(
            paciente_nombre="Paciente Sin Medico",
            cama="Observación 3",
            tipo_examen=self.examen_activo,
            medico_solicitante=None,
        )
        self.client.login(username="laboratorio", password="demo12345")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paciente Sin Medico")
        self.assertContains(response, "N/A")

    def test_login_responde_con_cabeceras_de_seguridad(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Content-Security-Policy", response)
        self.assertIn("Permissions-Policy", response)
        self.assertNotIn("cdn.jsdelivr.net", response["Content-Security-Policy"])
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(
            response["X-Content-Type-Options"],
            "nosniff",
        )

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
    )
    def test_redireccion_http_a_https_conserva_cabeceras_de_seguridad(self):
        response = self.client.get(reverse("login"), secure=False)
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].startswith("https://"))
        self.assertIn("Content-Security-Policy", response)
        self.assertIn("Permissions-Policy", response)
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")


class DatosFicticiosCommandTests(TestCase):
    def test_generar_datos_ficticios_crea_estados_y_pdfs(self):
        call_command("generar_datos_ficticios", "--limpiar-demo")

        ordenes = OrdenExamen.objects.filter(paciente_nombre__startswith="DEMO - ")
        self.assertEqual(ordenes.count(), 9)
        self.assertTrue(ordenes.filter(estado="SOLICITADO").exists())
        self.assertTrue(ordenes.filter(estado="TOMADO").exists())
        self.assertTrue(ordenes.filter(estado="ENVIADO").exists())
        self.assertTrue(
            ordenes.filter(estado="RESULTADO", archivo_resultado__isnull=False).exists()
        )
        self.assertTrue(
            EventoOrden.objects.filter(
                orden__paciente_nombre__startswith="DEMO - ",
                tipo_evento="PDF",
            ).exists()
        )
