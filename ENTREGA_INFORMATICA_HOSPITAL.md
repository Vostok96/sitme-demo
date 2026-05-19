# Entrega Técnica del Proyecto SITME

## Qué se debe entregar

Para que el área de Informática pueda recibir, revisar y desplegar el proyecto con orden, la entrega debe incluir:

1. Código fuente completo del proyecto.
2. Archivo de variables de entorno de ejemplo: `.env.example`.
3. Dependencias del proyecto: `requirements.txt`.
4. Archivos de despliegue: `Dockerfile` y `docker-compose.yml`.
5. Carpeta de la aplicación Django:
   - `sitme_core/`
   - `tracking/`
6. Script principal: `manage.py`.
7. Documento técnico o instructivo de despliegue.
8. Respaldo de base de datos y carpeta `media/` solo si se desea migrar información ya cargada.

## Aclaración importante sobre el entorno actual

La instancia publicada en `https://sitme.microbiolog-ia.com/` fue levantada como entorno demostrativo en un servidor NAS particular para sustentar el funcionamiento del sistema ante Dirección y jefaturas sin depender de un entorno de desarrollo local.

No constituye el hosting institucional definitivo. La instalación formal debe realizarse en la infraestructura, dominio y políticas de seguridad administradas por el Hospital Víctor Ramos Guardia.

## Qué no conviene entregar dentro del paquete principal

No conviene incluir en la primera entrega:

1. `venv/`
2. `staticfiles/`
3. archivos temporales de Office como `~$...`
4. respaldos locales antiguos
5. secretos reales del entorno (`.env` con claves reales)

## Información mínima que debes decir al área de Informática

Puedes explicar el proyecto así:

> SITME es una aplicación web desarrollada en Django para el registro, seguimiento en tiempo real y trazabilidad de solicitudes de laboratorio y muestras epidemiológicas. Permite registrar órdenes, actualizar estados, consultar historial, administrar usuarios por roles y cargar o descargar resultados PDF de forma controlada. Actualmente usa SQLite y almacenamiento local de archivos, con despliegue en contenedor Docker.

También puedes añadir esta precisión:

> La publicación en el dominio personal se utilizó únicamente para demostrar operatividad funcional ante usuarios no técnicos. La entrega actual corresponde al código fuente, configuración de despliegue y lineamientos necesarios para que el área de Informática realice la instalación oficial bajo dominio y hosting institucional.

## Requisitos del hosting o servidor

El área de Informática debería prever:

1. Python 3.12 o despliegue mediante Docker.
2. Un dominio o subdominio institucional.
3. Certificado HTTPS válido.
4. Proxy reverso con cabecera `X-Forwarded-Proto`.
5. Persistencia para:
   - base de datos
   - carpeta `media/`
6. Respaldo periódico de base de datos y archivos PDF.

## Variables de entorno necesarias

Como mínimo deben definir:

1. `DJANGO_SECRET_KEY`
2. `DJANGO_DEBUG=False`
3. `DJANGO_ENABLE_HTTPS_SECURITY=True`
4. `DJANGO_ALLOWED_HOSTS`
5. `DJANGO_CSRF_TRUSTED_ORIGINS`
6. `DJANGO_TIME_ZONE=America/Lima`

## Pasos de despliegue sugeridos

1. Copiar el proyecto al servidor institucional.
2. Crear el archivo `.env` a partir de `.env.example`.
3. Ejecutar:

```bash
docker compose up -d --build
docker compose exec sitme_web python manage.py migrate
docker compose exec sitme_web python manage.py collectstatic --noinput
```

4. Verificar acceso web y login.
5. Crear o migrar usuarios.
6. Restaurar `db.sqlite3` y `media/` solo si se trasladará la información existente.

## Recomendaciones de mejora para la instalación institucional

Si Informática lo considera pertinente, a mediano plazo conviene:

1. Migrar de SQLite a PostgreSQL.
2. Integrar copias de seguridad automáticas.
3. Mantener el sistema detrás de HTTPS obligatorio.
4. Restringir acceso administrativo por red interna o VPN si aplica.
5. Registrar responsable técnico de mantenimiento y actualizaciones.

## Observación importante sobre la migración

Si el hospital desea continuar exactamente con la información actual, además del código debe recibir:

1. una copia actualizada de `db.sqlite3`
2. la carpeta `media/`

Si desean empezar limpio, basta con el código, migraciones y variables de entorno.
