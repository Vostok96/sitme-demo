from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from tracking.models import CatalogoExamen, EventoOrden, OrdenExamen
from tracking.permissions import GRUPO_EPIDEMIOLOGIA, GRUPO_LABORATORIO, GRUPO_MEDICO
from tracking.views import registrar_evento


PDF_MINIMO = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 57 >>
stream
BT
/F1 12 Tf
40 90 Td
(Resultado ficticio SITME) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000241 00000 n 
0000000348 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
418
%%EOF
"""


class Command(BaseCommand):
    help = 'Genera pacientes ficticios con distintos estados y PDFs de prueba para validar SITME.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpiar-demo',
            action='store_true',
            help='Elimina las órdenes ficticias previas antes de volver a generarlas.',
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            usuarios = self._asegurar_usuarios()
            examenes = self._asegurar_examenes()

            if options['limpiar_demo']:
                self._limpiar_demo()

            data = [
                ('DEMO - Ana Pérez', 'Pediatría - Cama 04', examenes['PCR Dengue'], 'SOLICITADO', usuarios['pediatria'], False, 'Paciente febril en observación.'),
                ('DEMO - Luis Quispe', 'UCIN - Incubadora 02', examenes['PCR Influenza'], 'TOMADO', usuarios['ucin'], False, 'Control neonatal por distrés respiratorio.'),
                ('DEMO - Marta Gómez', 'Intermedios I - Cama 07', examenes['Serología Leptospira'], 'ENVIADO', usuarios['intermedios_i'], False, 'Muestra enviada a referencia regional.'),
                ('DEMO - José Huamán', 'Intermedios II - Cama 12', examenes['PCR COVID-19'], 'RESULTADO', usuarios['intermedios_ii'], True, 'Resultado recibido y listo para descarga.'),
                ('DEMO - Rosa Chávez', 'Metaxénicas - Box 01', examenes['Gota Gruesa Malaria'], 'RESULTADO', usuarios['metaxenicas'], True, 'Caso sospechoso de malaria importada.'),
                ('DEMO - Miguel Rojas', 'Unidad de Traumashock - Tópico 03', examenes['PCR Meningococo'], 'TOMADO', usuarios['traumashock'], False, 'Paciente crítico con sospecha infecciosa.'),
                ('DEMO - Elena Flores', 'Consultorio Externo - Box 05', examenes['ELISA VIH'], 'SOLICITADO', usuarios['consultorio_externo'], False, 'Tamizaje ambulatorio.'),
                ('DEMO - Pedro Ramírez', 'Hospitalización - Cama 21', examenes['Panel Respiratorio'], 'ENVIADO', usuarios['hospitalizacion'], False, 'Seguimiento clínico con envío diario.'),
                ('DEMO - Carla Salazar', 'Emergencia - Camilla 09', examenes['PCR Dengue'], 'RESULTADO', usuarios['emergencia'], True, 'Resultado urgente recibido el mismo día.'),
            ]

            creadas = 0
            for nombre, cama, examen, estado, solicitante, con_pdf, notas in data:
                orden, created = OrdenExamen.objects.get_or_create(
                    paciente_nombre=nombre,
                    defaults={
                        'cama': cama,
                        'tipo_examen': examen,
                        'estado': 'SOLICITADO',
                        'medico_solicitante': solicitante,
                        'notas': notas,
                    },
                )
                if created:
                    registrar_evento(
                        orden,
                        'CREACION',
                        'Solicitud ficticia generada para validación funcional.',
                        usuario=solicitante,
                        estado_nuevo='SOLICITADO',
                    )
                    creadas += 1
                else:
                    orden.cama = cama
                    orden.tipo_examen = examen
                    orden.medico_solicitante = solicitante
                    orden.notas = notas
                    orden.save()

                self._aplicar_estado(orden, estado, usuarios['dgallardo'])

                if con_pdf:
                    self._adjuntar_pdf(orden, nombre)

            self.stdout.write(self.style.SUCCESS(f'Se dejaron listas {len(data)} órdenes ficticias ({creadas} nuevas).'))
            self.stdout.write('Estados cubiertos: SOLICITADO, TOMADO, ENVIADO y RESULTADO.')

    def _asegurar_usuarios(self):
        grupos = {
            GRUPO_LABORATORIO: Group.objects.get_or_create(name=GRUPO_LABORATORIO)[0],
            GRUPO_EPIDEMIOLOGIA: Group.objects.get_or_create(name=GRUPO_EPIDEMIOLOGIA)[0],
            GRUPO_MEDICO: Group.objects.get_or_create(name=GRUPO_MEDICO)[0],
        }
        specs = {
            'dgallardo': ('Denis Gallardo', GRUPO_LABORATORIO),
            'pediatria': ('Pediatría', GRUPO_MEDICO),
            'ucin': ('UCIN', GRUPO_MEDICO),
            'intermedios_i': ('Intermedios I', GRUPO_MEDICO),
            'intermedios_ii': ('Intermedios II', GRUPO_MEDICO),
            'metaxenicas': ('Metaxénicas', GRUPO_MEDICO),
            'traumashock': ('Unidad de Traumashock', GRUPO_MEDICO),
            'consultorio_externo': ('Consultorio Externo', GRUPO_MEDICO),
            'hospitalizacion': ('Hospitalización', GRUPO_MEDICO),
            'emergencia': ('Emergencia', GRUPO_MEDICO),
            'epidemiologia': ('Epidemiología', GRUPO_EPIDEMIOLOGIA),
        }

        usuarios = {}
        for username, (first_name, grupo) in specs.items():
            user, _ = User.objects.get_or_create(username=username)
            user.first_name = first_name
            user.is_active = True
            user.is_staff = grupo == GRUPO_LABORATORIO
            user.is_superuser = False
            if not user.password:
                user.set_password('Demo12345!')
            user.save()
            user.groups.set([grupos[grupo]])
            usuarios[username] = user
        return usuarios

    def _asegurar_examenes(self):
        nombres = [
            'PCR Dengue',
            'PCR Influenza',
            'Serología Leptospira',
            'PCR COVID-19',
            'Gota Gruesa Malaria',
            'PCR Meningococo',
            'ELISA VIH',
            'Panel Respiratorio',
        ]
        examenes = {}
        for nombre in nombres:
            examenes[nombre], _ = CatalogoExamen.objects.get_or_create(nombre=nombre, defaults={'activo': True})
        return examenes

    def _limpiar_demo(self):
        OrdenExamen.objects.filter(paciente_nombre__startswith='DEMO - ').delete()

    def _aplicar_estado(self, orden, estado_objetivo, laboratorista):
        if orden.estado != 'SOLICITADO' and not EventoOrden.objects.filter(orden=orden, tipo_evento='CAMBIO_ESTADO').exists():
            orden.estado = 'SOLICITADO'
            orden.fecha_toma = None
            orden.fecha_envio = None
            orden.fecha_resultado = None
            orden.laboratorista_toma = None
            orden.laboratorista_envio = None
            orden.laboratorista_resultado = None

        flujo = ['SOLICITADO', 'TOMADO', 'ENVIADO', 'RESULTADO']
        objetivo = flujo.index(estado_objetivo)
        orden.estado = 'SOLICITADO'
        orden.fecha_toma = None
        orden.fecha_envio = None
        orden.fecha_resultado = None
        orden.laboratorista_toma = None
        orden.laboratorista_envio = None
        orden.laboratorista_resultado = None
        orden.save()
        orden.eventos.exclude(tipo_evento='CREACION').delete()

        for indice in range(1, objetivo + 1):
            anterior = flujo[indice - 1]
            nuevo = flujo[indice]
            orden.estado = nuevo
            if nuevo == 'TOMADO':
                orden.laboratorista_toma = laboratorista
                orden.fecha_toma = orden.fecha_toma or orden.fecha_solicitud
            elif nuevo == 'ENVIADO':
                orden.laboratorista_envio = laboratorista
                orden.fecha_envio = orden.fecha_envio or orden.fecha_solicitud
            elif nuevo == 'RESULTADO':
                orden.laboratorista_resultado = laboratorista
                orden.fecha_resultado = orden.fecha_resultado or orden.fecha_solicitud
            orden.save()
            registrar_evento(
                orden,
                'CAMBIO_ESTADO',
                f'Estado ficticio ajustado de {anterior} a {nuevo}.',
                usuario=laboratorista,
                estado_anterior=anterior,
                estado_nuevo=nuevo,
            )

    def _adjuntar_pdf(self, orden, paciente_nombre):
        if orden.archivo_resultado:
            orden.archivo_resultado.delete(save=False)

        filename = paciente_nombre.lower().replace(' ', '_').replace('-', '').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u') + '.pdf'
        orden.archivo_resultado.save(filename, ContentFile(PDF_MINIMO), save=False)
        orden.save()
        registrar_evento(
            orden,
            'PDF',
            'Resultado PDF ficticio cargado para pruebas.',
            usuario=orden.laboratorista_resultado or orden.laboratorista_envio or orden.laboratorista_toma,
            estado_anterior='RESULTADO',
            estado_nuevo='RESULTADO',
        )
